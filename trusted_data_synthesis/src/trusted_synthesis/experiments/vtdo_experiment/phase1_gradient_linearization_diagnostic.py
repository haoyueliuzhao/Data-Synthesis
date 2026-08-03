from __future__ import annotations

import argparse
import gc
import json
import math
import os
import statistics
import time
from collections import defaultdict
from pathlib import Path
from typing import Any

from trusted_synthesis.experiments.vtdo_experiment.phase1_contribution_gradient import (
    _gradient_norm,
    _load_jsonl,
    _load_verified_gradient,
    _normalized_gradient_alignment,
    _record_gradient,
    _sha256,
    _valid_hashed_row,
    _weighted_gradient,
)
from trusted_synthesis.experiments.vtdo_experiment.phase1_distribution_intervention import (
    DISTRIBUTION_INTERVENTION_VERSION,
    _apply_gradient_step,
    _gradient_artifact_map,
    _rank_evidence,
)
from trusted_synthesis.experiments.vtdo_experiment.phase1_probe_gpu import (
    _adapter_tensor_sha256,
    _baseline_lora_model,
    _evaluate,
    _load_records,
    _load_tokenizer,
    _read_json,
    _seed_everything,
    _write_json,
)
from trusted_synthesis.hashing import canonical_hash

LINEARIZATION_DIAGNOSTIC_VERSION = "finance_gradient_linearization_diagnostic.v3"
DIAGNOSTIC_NUMERIC_SEED = 20260891
PARAMETER_STEP_MINIMUM_COSINE = 0.9
PARAMETER_STEP_MAXIMUM_RELATIVE_ERROR = 0.1
PARAMETER_STEP_MINIMUM_NONZERO_RECOVERY = 0.9
PARAMETER_STEP_MINIMUM_ENERGY_RECOVERY = 0.9


def _worker_rows(output_dir: Path) -> list[dict[str, Any]]:
    return [
        row
        for path in sorted((output_dir / "workers").glob("*.jsonl"))
        for row in _load_jsonl(path)
    ]


def _single_numeric_value(rows: list[dict[str, Any]], field: str) -> float:
    values = {float(row[field]) for row in rows}
    if len(values) != 1:
        raise ValueError(f"linearization diagnostic found inconsistent {field}")
    return values.pop()


def _single_string_value(rows: list[dict[str, Any]], field: str) -> str:
    values = {str(row[field]) for row in rows}
    if len(values) != 1:
        raise ValueError(f"linearization diagnostic found inconsistent {field}")
    return values.pop()


def _pearson(left: list[float], right: list[float]) -> float:
    if len(left) != len(right) or len(left) < 2:
        raise ValueError("linearization diagnostic correlation inputs are incomplete")
    left_mean = statistics.fmean(left)
    right_mean = statistics.fmean(right)
    numerator = sum(
        (left_value - left_mean) * (right_value - right_mean)
        for left_value, right_value in zip(left, right, strict=True)
    )
    left_scale = math.sqrt(sum((value - left_mean) ** 2 for value in left))
    right_scale = math.sqrt(sum((value - right_mean) ** 2 for value in right))
    if not left_scale > 0 or not right_scale > 0:
        raise ValueError("linearization diagnostic correlation has zero variance")
    return numerator / (left_scale * right_scale)


def _parameter_step_fidelity(
    initial_parameters: dict[str, Any],
    baseline_parameters: dict[str, Any],
    global_gradient: dict[str, Any],
    direction: dict[str, Any],
    *,
    learning_rate: float,
    directional_scale: float,
) -> dict[str, float | int]:
    """Replay the float32 intervention and compare it with its real-valued step."""

    import torch

    names = tuple(initial_parameters)
    if (
        not names
        or tuple(baseline_parameters) != names
        or tuple(global_gradient) != names
        or tuple(direction) != names
    ):
        raise ValueError("parameter-step diagnostic parameter manifests do not align")
    if learning_rate <= 0 or not math.isfinite(learning_rate):
        raise ValueError("parameter-step diagnostic requires a positive learning rate")
    if directional_scale <= 0 or not math.isfinite(directional_scale):
        raise ValueError("parameter-step diagnostic requires a positive directional scale")

    dot = 0.0
    actual_squared_norm = 0.0
    intended_squared_norm = 0.0
    error_squared_norm = 0.0
    total_parameter_count = 0
    intended_nonzero_count = 0
    recovered_nonzero_count = 0
    actual_nonzero_count = 0
    recovered_intended_squared_norm = 0.0
    maximum_absolute_error = 0.0
    with torch.no_grad():
        for name in names:
            initial = initial_parameters[name]
            baseline = baseline_parameters[name]
            global_value = global_gradient[name]
            direction_value = direction[name]
            if (
                baseline.shape != initial.shape
                or global_value.shape != initial.shape
                or direction_value.shape != initial.shape
            ):
                raise ValueError(f"parameter-step diagnostic shape mismatch:{name}")
            if not (
                torch.isfinite(initial).all()
                and torch.isfinite(baseline).all()
                and torch.isfinite(global_value).all()
                and torch.isfinite(direction_value).all()
            ):
                raise ValueError(f"parameter-step diagnostic non-finite tensor:{name}")

            expected_baseline = initial.detach().clone()
            expected_baseline.add_(
                global_value.to(device=initial.device, dtype=initial.dtype),
                alpha=-learning_rate,
            )
            if not torch.equal(expected_baseline, baseline):
                raise ValueError(f"parameter-step diagnostic baseline replay mismatch:{name}")

            perturbed = initial.detach().clone()
            perturbed_gradient = global_value.to(
                device=initial.device,
                dtype=initial.dtype,
            ).clone()
            perturbed_gradient.add_(
                direction_value.to(device=initial.device, dtype=initial.dtype),
                alpha=directional_scale,
            )
            perturbed.add_(perturbed_gradient, alpha=-learning_rate)

            actual = (perturbed - baseline).to(dtype=torch.float64)
            intended = direction_value.to(
                device=initial.device,
                dtype=torch.float64,
            ) * (-learning_rate * directional_scale)
            error = actual - intended
            actual_flat = actual.reshape(-1)
            intended_flat = intended.reshape(-1)
            error_flat = error.reshape(-1)
            dot += float(torch.dot(actual_flat, intended_flat).item())
            actual_squared_norm += float(torch.dot(actual_flat, actual_flat).item())
            intended_squared_norm += float(torch.dot(intended_flat, intended_flat).item())
            error_squared_norm += float(torch.dot(error_flat, error_flat).item())
            intended_mask = intended_flat != 0
            actual_mask = actual_flat != 0
            total_parameter_count += intended_flat.numel()
            intended_nonzero_count += int(intended_mask.sum().item())
            actual_nonzero_count += int(actual_mask.sum().item())
            recovered_nonzero_count += int((intended_mask & actual_mask).sum().item())
            recovered_intended = intended_flat[actual_mask]
            recovered_intended_squared_norm += float(
                torch.dot(recovered_intended, recovered_intended).item()
            )
            maximum_absolute_error = max(
                maximum_absolute_error,
                float(error_flat.abs().max().item()),
            )

    intended_norm = math.sqrt(intended_squared_norm)
    actual_norm = math.sqrt(actual_squared_norm)
    if not intended_norm > 0:
        raise ValueError("parameter-step diagnostic has a zero intended perturbation")
    cosine = dot / (actual_norm * intended_norm) if actual_norm > 0 else 0.0
    return {
        "parameter_count": total_parameter_count,
        "intended_nonzero_count": intended_nonzero_count,
        "actual_nonzero_count": actual_nonzero_count,
        "recovered_nonzero_count": recovered_nonzero_count,
        "intended_step_norm": intended_norm,
        "actual_step_norm": actual_norm,
        "parameter_step_cosine": cosine,
        "parameter_step_norm_ratio": actual_norm / intended_norm,
        "parameter_step_relative_error": math.sqrt(error_squared_norm) / intended_norm,
        "parameter_step_nonzero_recovery": (
            recovered_nonzero_count / intended_nonzero_count
            if intended_nonzero_count
            else 0.0
        ),
        "parameter_step_energy_recovery": (
            recovered_intended_squared_norm / intended_squared_norm
        ),
        "maximum_absolute_step_error": maximum_absolute_error,
    }


def run(args: argparse.Namespace) -> None:
    os.environ["CUDA_VISIBLE_DEVICES"] = str(args.gpu_id)
    import torch
    from safetensors.torch import save_file

    output_dir = Path(args.output_dir).resolve()
    plan = _read_json(output_dir / "plan.json")
    report = _read_json(output_dir / "report.json")
    if plan.get("experiment_version") != DISTRIBUTION_INTERVENTION_VERSION:
        raise ValueError("linearization diagnostic requires a current intervention plan")
    if report.get("plan_hash") != plan.get("plan_hash"):
        raise ValueError("linearization diagnostic report does not replay its plan")
    if report.get("production_authorized") is not False:
        raise ValueError("linearization diagnostic requires an unpromoted experiment")
    gradient_report = _read_json(Path(plan["source_gradient_report_path"]))
    if gradient_report.get("report_hash") != plan.get("source_gradient_report_hash"):
        raise ValueError("linearization diagnostic source Gradient report changed")
    rows = _worker_rows(output_dir)
    expected = int(plan["state_count"]) * len(plan["intervention_seeds"])
    if len(rows) != expected:
        raise ValueError("linearization diagnostic requires the complete intervention matrix")
    if any(
        not _valid_hashed_row(row, prefix="finance_distribution_intervention_result:")
        for row in rows
    ):
        raise ValueError("linearization diagnostic intervention identity failed replay")
    baseline_adapter_hash = _single_string_value(
        rows,
        "baseline_adapter_tensor_sha256",
    )
    expected_baseline_loss = _single_numeric_value(rows, "baseline_loss")
    expected_baseline_performance = _single_numeric_value(rows, "baseline_performance")
    expected_final_tokens = int(_single_numeric_value(rows, "final_test_supervised_tokens"))

    started = time.monotonic()
    _seed_everything(DIAGNOSTIC_NUMERIC_SEED)
    torch.cuda.reset_peak_memory_stats()
    tokenizer = _load_tokenizer(Path(plan["model_dir"]))
    model = _baseline_lora_model(
        Path(plan["model_dir"]),
        Path(plan["beneficiary_adapter_dir"]),
    )
    if _adapter_tensor_sha256(model) != plan["beneficiary_adapter_tensor_sha256"]:
        raise ValueError("linearization diagnostic loaded another beneficiary Adapter")
    initial_parameters = {
        name: parameter.detach().clone()
        for name, parameter in sorted(model.named_parameters())
        if parameter.requires_grad
    }
    global_artifact = plan["global_gradient_artifact"]
    global_gradient = _load_verified_gradient(
        Path(global_artifact["file"]),
        str(global_artifact["sha256"]),
    )
    if tuple(initial_parameters) != tuple(global_gradient):
        raise ValueError("linearization diagnostic parameter manifest changed")
    global_gradient_gpu = {
        name: value.to(
            device=initial_parameters[name].device,
            dtype=initial_parameters[name].dtype,
            non_blocking=False,
        )
        for name, value in global_gradient.items()
    }
    _apply_gradient_step(
        model,
        global_gradient,
        learning_rate=float(plan["learning_rate"]),
    )
    if _adapter_tensor_sha256(model) != baseline_adapter_hash:
        raise ValueError("linearization diagnostic baseline checkpoint failed replay")
    baseline_parameters = {
        name: parameter.detach().clone()
        for name, parameter in sorted(model.named_parameters())
        if parameter.requires_grad
    }

    source_records = _load_records(Path(plan["source_records_path"]))
    final_records = tuple(
        source_records[record_id] for record_id in plan["final_test_record_ids"]
    )
    baseline_performance, baseline_loss, baseline_tokens = _evaluate(
        model,
        tokenizer,
        final_records,
    )
    if baseline_tokens != expected_final_tokens:
        raise ValueError("linearization diagnostic changed final-test token support")
    if not math.isclose(baseline_loss, expected_baseline_loss, abs_tol=1e-8):
        raise ValueError("linearization diagnostic baseline loss failed replay")
    if not math.isclose(baseline_performance, expected_baseline_performance, abs_tol=1e-8):
        raise ValueError("linearization diagnostic baseline utility failed replay")

    diagnostic_dir = output_dir / "linearization_diagnostic"
    diagnostic_dir.mkdir(parents=True, exist_ok=True)
    record_gradients: list[dict[str, Any]] = []
    record_rows: list[dict[str, Any]] = []
    record_weights: list[float] = []
    for index, record in enumerate(final_records):
        gradient, loss, supervised_tokens = _record_gradient(model, tokenizer, record)
        path = diagnostic_dir / f"final_record_{index:02d}.safetensors"
        save_file(gradient, path)
        record_gradients.append(gradient)
        record_weights.append(float(supervised_tokens))
        record_rows.append(
            {
                "record_id": record.record_id,
                "file": str(path),
                "sha256": _sha256(path),
                "loss": loss,
                "supervised_tokens": supervised_tokens,
                "gradient_norm": _gradient_norm(gradient),
            }
        )
    final_gradient = _weighted_gradient(record_gradients, record_weights)
    final_gradient_path = diagnostic_dir / "final_test_aggregate.safetensors"
    save_file(final_gradient, final_gradient_path)
    final_gradient_sha256 = _sha256(final_gradient_path)
    final_gradient_gpu = {
        name: value.to(device="cuda:0", non_blocking=False)
        for name, value in final_gradient.items()
    }
    final_gradient_norm = _gradient_norm(final_gradient_gpu)

    task_artifacts = _gradient_artifact_map(
        plan["task_gradient_artifacts"],
        key="task_id",
    )
    state_artifacts = _gradient_artifact_map(
        plan["state_gradient_artifacts"],
        key="job_id",
    )
    observed = {
        (str(row["task_id"]), str(row["state_id"])): float(
            row["intervention_mean_contribution"]
        )
        for row in report["state_rows"]
    }
    state_rows: list[dict[str, Any]] = []
    grouped: defaultdict[str, list[dict[str, Any]]] = defaultdict(list)
    for task in plan["task_jobs"]:
        task_id = str(task["task_id"])
        task_artifact = task_artifacts[task_id]
        task_gradient = _load_verified_gradient(
            Path(task_artifact["file"]),
            str(task_artifact["sha256"]),
        )
        for state in task["states"]:
            state_id = str(state["state_id"])
            state_artifact = state_artifacts[str(state["job_id"])]
            state_gradient = _load_verified_gradient(
                Path(state_artifact["state_gradient_file"]),
                str(state_artifact["state_gradient_sha256"]),
            )
            direction_gpu = {
                name: (state_gradient[name] - task_gradient[name]).to(
                    device="cuda:0",
                    non_blocking=False,
                )
                for name in task_gradient
            }
            direction_norm = _gradient_norm(direction_gpu)
            dot, cosine = _normalized_gradient_alignment(
                direction_gpu,
                final_gradient_gpu,
                left_norm=direction_norm,
                right_norm=final_gradient_norm,
            )
            directional_scale = float(plan["task_marginals"][task_id]) * float(
                plan["epsilon"]
            )
            parameter_step_fidelity = _parameter_step_fidelity(
                initial_parameters,
                baseline_parameters,
                global_gradient_gpu,
                direction_gpu,
                learning_rate=float(plan["learning_rate"]),
                directional_scale=directional_scale,
            )
            predicted = float(plan["learning_rate"]) * dot
            actual = observed[(task_id, state_id)]
            row = {
                "task_id": task_id,
                "task_type": task["task_type"],
                "state_id": state_id,
                "strategy": state["strategy"],
                "first_order_directional_dot": dot,
                "first_order_cosine": cosine,
                "first_order_predicted_contribution": predicted,
                "intervention_mean_contribution": actual,
                "absolute_prediction_error": abs(predicted - actual),
                "directional_scale": directional_scale,
                **parameter_step_fidelity,
            }
            state_rows.append(row)
            grouped[task_id].append(row)
            del direction_gpu, state_gradient
        del task_gradient
    rank_evidence = _rank_evidence(
        grouped,
        estimator_field="first_order_predicted_contribution",
        target_field="intervention_mean_contribution",
        seed=DIAGNOSTIC_NUMERIC_SEED + 1,
    )
    predicted_values = [float(row["first_order_predicted_contribution"]) for row in state_rows]
    actual_values = [float(row["intervention_mean_contribution"]) for row in state_rows]
    mechanism_consistent = bool(rank_evidence["passes_rank_gate"])
    step_cosines = [float(row["parameter_step_cosine"]) for row in state_rows]
    step_norm_ratios = [float(row["parameter_step_norm_ratio"]) for row in state_rows]
    step_relative_errors = [
        float(row["parameter_step_relative_error"]) for row in state_rows
    ]
    step_nonzero_recoveries = [
        float(row["parameter_step_nonzero_recovery"]) for row in state_rows
    ]
    step_energy_recoveries = [
        float(row["parameter_step_energy_recovery"]) for row in state_rows
    ]
    parameter_step_summary = {
        "minimum_cosine_threshold": PARAMETER_STEP_MINIMUM_COSINE,
        "maximum_relative_error_threshold": PARAMETER_STEP_MAXIMUM_RELATIVE_ERROR,
        "minimum_nonzero_recovery_threshold": PARAMETER_STEP_MINIMUM_NONZERO_RECOVERY,
        "minimum_energy_recovery_threshold": PARAMETER_STEP_MINIMUM_ENERGY_RECOVERY,
        "minimum_cosine": min(step_cosines),
        "median_cosine": statistics.median(step_cosines),
        "minimum_norm_ratio": min(step_norm_ratios),
        "median_norm_ratio": statistics.median(step_norm_ratios),
        "maximum_norm_ratio": max(step_norm_ratios),
        "maximum_relative_error": max(step_relative_errors),
        "median_relative_error": statistics.median(step_relative_errors),
        "minimum_nonzero_recovery": min(step_nonzero_recoveries),
        "median_nonzero_recovery": statistics.median(step_nonzero_recoveries),
        "minimum_energy_recovery": min(step_energy_recoveries),
        "median_energy_recovery": statistics.median(step_energy_recoveries),
    }
    parameter_step_identifiable = bool(
        parameter_step_summary["median_cosine"] >= PARAMETER_STEP_MINIMUM_COSINE
        and parameter_step_summary["median_relative_error"]
        <= PARAMETER_STEP_MAXIMUM_RELATIVE_ERROR
        and parameter_step_summary["median_nonzero_recovery"]
        >= PARAMETER_STEP_MINIMUM_NONZERO_RECOVERY
        and parameter_step_summary["median_energy_recovery"]
        >= PARAMETER_STEP_MINIMUM_ENERGY_RECOVERY
    )
    manifest: dict[str, Any] = {
        "diagnostic_version": LINEARIZATION_DIAGNOSTIC_VERSION,
        "role": "post_hoc_mechanism_diagnostic_only",
        "uses_untouched_final_test_gradient": True,
        "cannot_authorize_production": True,
        "intervention_plan_hash": plan["plan_hash"],
        "intervention_report_hash": report["report_hash"],
        "source_gradient_report_hash": gradient_report["report_hash"],
        "baseline_adapter_tensor_sha256": baseline_adapter_hash,
        "baseline_loss": baseline_loss,
        "baseline_performance": baseline_performance,
        "final_test_supervised_tokens": baseline_tokens,
        "final_test_record_gradients": record_rows,
        "final_test_aggregate_gradient": {
            "file": str(final_gradient_path),
            "sha256": final_gradient_sha256,
            "gradient_norm": final_gradient_norm,
            "weighting": "supervised_token_count",
        },
        "state_count": len(state_rows),
        "task_count": len(grouped),
        "rank_evidence": rank_evidence,
        "global_pearson": _pearson(predicted_values, actual_values),
        "mean_absolute_prediction_error": statistics.fmean(
            float(row["absolute_prediction_error"]) for row in state_rows
        ),
        "mechanism_consistent": mechanism_consistent,
        "parameter_step_identifiable": parameter_step_identifiable,
        "parameter_step_summary": parameter_step_summary,
        "diagnostic_interpretation": (
            "intervention_below_parameter_numeric_resolution"
            if not parameter_step_identifiable
            else (
                "first_order_mechanics_supported_but_support_gradient_not_representative"
                if mechanism_consistent
                else "first_order_linearization_mismatch_on_identifiable_parameter_steps"
            )
        ),
        "state_rows": state_rows,
        "runtime_seconds": time.monotonic() - started,
        "peak_gpu_memory_bytes": int(torch.cuda.max_memory_allocated()),
        "numeric_seed": DIAGNOSTIC_NUMERIC_SEED,
        "claim_boundary": (
            "This diagnostic directly uses the final-test gradient after observing a failed "
            "independent intervention. It may localize the failure mechanism but must never "
            "serve as a Contribution estimator, promotion gate, or hyperparameter selector."
        ),
    }
    manifest["diagnostic_hash"] = canonical_hash(
        manifest,
        prefix="finance_gradient_linearization_diagnostic:",
    )
    _write_json(diagnostic_dir / "report.json", manifest)
    print(json.dumps(manifest, ensure_ascii=False, indent=2, sort_keys=True))
    del (
        model,
        global_gradient,
        global_gradient_gpu,
        final_gradient,
        final_gradient_gpu,
        record_gradients,
        initial_parameters,
        baseline_parameters,
    )
    gc.collect()
    torch.cuda.empty_cache()


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Diagnose Scheme 3 linearization at the baseline-updated checkpoint"
    )
    parser.add_argument("--output-dir", required=True)
    parser.add_argument("--gpu-id", type=int, default=0)
    return parser


def main() -> None:
    run(_parser().parse_args())


if __name__ == "__main__":
    main()
