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
    GRADIENT_ALIGNMENT_VERSION,
    _append_jsonl,
    _gradient_norm,
    _load_jsonl,
    _load_verified_gradient,
    _sha256,
    _valid_hashed_row,
)
from trusted_synthesis.experiments.vtdo_experiment.phase1_distribution_intervention import (
    _apply_gradient_step,
    _rank_evidence,
    _restore_adapter,
)
from trusted_synthesis.experiments.vtdo_experiment.phase1_gradient_linearization_diagnostic import (
    _parameter_step_fidelity,
    _pearson,
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

BATCH_INTERVENTION_VERSION = "finance_batch_symmetric_intervention.v1"
BATCH_INTERVENTION_NUMERIC_SEED = 20260893
HADAMARD_ORDER = 64
CONTRASTS_PER_TASK = 2
STATE_COUNT_PER_TASK = 3
DEFAULT_EPSILON = 0.4
DEFAULT_LEARNING_RATE_CANDIDATES = (5e-5, 1e-4, 2e-4, 5e-4)
NUMERIC_REPLAY_ROW_INDICES = (0, 15, 31, 47)

PREFLIGHT_MINIMUM_MEDIAN_COSINE = 0.95
PREFLIGHT_MAXIMUM_MEDIAN_RELATIVE_ERROR = 0.25
PREFLIGHT_MINIMUM_MEDIAN_ENERGY_RECOVERY = 0.90
PREFLIGHT_MINIMUM_ROW_COSINE = 0.80
PREFLIGHT_MAXIMUM_ROW_RELATIVE_ERROR = 0.75
MAXIMUM_RECONSTRUCTION_RELATIVE_ERROR = 0.50

CONTRAST_BASIS: tuple[tuple[float, ...], ...] = (
    (0.5, -0.5, 0.0),
    (0.25, 0.25, -0.5),
)


def _sylvester_hadamard(order: int) -> tuple[tuple[int, ...], ...]:
    if order < 1 or order & (order - 1):
        raise ValueError("Hadamard order must be a positive power of two")
    matrix: tuple[tuple[int, ...], ...] = ((1,),)
    while len(matrix) < order:
        matrix = tuple(
            tuple(row) + tuple(row) for row in matrix
        ) + tuple(
            tuple(row) + tuple(-value for value in row) for row in matrix
        )
    return matrix


def _contrast_weights(sign_a: int, sign_b: int) -> tuple[float, float, float]:
    if sign_a not in (-1, 1) or sign_b not in (-1, 1):
        raise ValueError("batch intervention contrast signs must be +/-1")
    return (
        sign_a * CONTRAST_BASIS[0][0] + sign_b * CONTRAST_BASIS[1][0],
        sign_a * CONTRAST_BASIS[0][1] + sign_b * CONTRAST_BASIS[1][1],
        sign_a * CONTRAST_BASIS[0][2] + sign_b * CONTRAST_BASIS[1][2],
    )


def _symmetric_probabilities(
    probabilities: tuple[float, ...],
    weights: tuple[float, ...],
    *,
    epsilon: float,
) -> tuple[tuple[float, ...], tuple[float, ...]]:
    if len(probabilities) != STATE_COUNT_PER_TASK or len(weights) != len(probabilities):
        raise ValueError("batch intervention requires three-state conditional support")
    if not 0 < epsilon < 0.5:
        raise ValueError("batch intervention epsilon must lie in (0, 0.5)")
    if any(value <= 0 or not math.isfinite(value) for value in probabilities):
        raise ValueError("batch intervention probabilities must be positive and finite")
    if not math.isclose(sum(probabilities), 1.0, abs_tol=1e-12):
        raise ValueError("batch intervention probabilities must sum to one")
    if not math.isclose(sum(weights), 0.0, abs_tol=1e-12):
        raise ValueError("batch intervention contrast must preserve conditional mass")
    plus = tuple(
        value + epsilon * weight
        for value, weight in zip(probabilities, weights, strict=True)
    )
    minus = tuple(
        value - epsilon * weight
        for value, weight in zip(probabilities, weights, strict=True)
    )
    if any(value <= 0 for value in plus + minus):
        raise ValueError("batch intervention removed accepted state support")
    if not math.isclose(sum(plus), 1.0, abs_tol=1e-12) or not math.isclose(
        sum(minus), 1.0, abs_tol=1e-12
    ):
        raise ValueError("batch intervention failed conditional mass conservation")
    return plus, minus


def _recover_centered_state_values(
    coordinate_a: float,
    coordinate_b: float,
    *,
    task_marginal: float,
) -> tuple[float, float, float]:
    if not 0 < task_marginal <= 1 or not math.isfinite(task_marginal):
        raise ValueError("batch intervention requires a valid task marginal")
    first = coordinate_a / task_marginal + (2.0 / 3.0) * coordinate_b / task_marginal
    second = -coordinate_a / task_marginal + (2.0 / 3.0) * coordinate_b / task_marginal
    third = -(4.0 / 3.0) * coordinate_b / task_marginal
    values = (first, second, third)
    if not math.isclose(sum(values), 0.0, abs_tol=1e-12):
        raise ValueError("batch intervention failed centered state reconstruction")
    return values


def _linear_gradient_combination(
    gradients: tuple[dict[str, Any], ...],
    coefficients: tuple[float, ...],
) -> dict[str, Any]:
    import torch

    if not gradients or len(gradients) != len(coefficients):
        raise ValueError("gradient combination inputs are incomplete")
    names = tuple(gradients[0])
    if not names or any(tuple(gradient) != names for gradient in gradients):
        raise ValueError("gradient combination parameter manifests do not align")
    result = {}
    for name in names:
        reference = gradients[0][name]
        if any(gradient[name].shape != reference.shape for gradient in gradients):
            raise ValueError(f"gradient combination shape mismatch:{name}")
        value = torch.zeros_like(reference)
        for coefficient, gradient in zip(coefficients, gradients, strict=True):
            value.add_(gradient[name], alpha=coefficient)
        if not torch.isfinite(value).all():
            raise ValueError(f"gradient combination produced non-finite values:{name}")
        result[name] = value.contiguous()
    return result


def _combine_coordinate_directions(
    coordinate_gradients: tuple[dict[str, Any], ...],
    signs: tuple[int, ...],
) -> dict[str, Any]:
    import torch

    if not coordinate_gradients or len(coordinate_gradients) != len(signs):
        raise ValueError("batch direction coordinate support is incomplete")
    names = tuple(coordinate_gradients[0])
    if any(tuple(gradient) != names for gradient in coordinate_gradients):
        raise ValueError("batch direction parameter manifests do not align")
    sign_tensor = torch.tensor(
        signs,
        dtype=coordinate_gradients[0][names[0]].dtype,
        device=coordinate_gradients[0][names[0]].device,
    )
    result = {}
    for name in names:
        stacked = torch.stack([gradient[name] for gradient in coordinate_gradients], dim=0)
        value = torch.tensordot(sign_tensor, stacked, dims=([0], [0])).contiguous()
        if not torch.isfinite(value).all():
            raise ValueError(f"batch direction produced non-finite values:{name}")
        result[name] = value
        del stacked
    return result


def _fidelity_summary(rows: list[dict[str, Any]]) -> dict[str, Any]:
    cosines = [float(row["parameter_step_cosine"]) for row in rows]
    relative_errors = [float(row["parameter_step_relative_error"]) for row in rows]
    energy_recoveries = [float(row["parameter_step_energy_recovery"]) for row in rows]
    summary: dict[str, Any] = {
        "observation_count": len(rows),
        "median_cosine": statistics.median(cosines),
        "minimum_cosine": min(cosines),
        "median_relative_error": statistics.median(relative_errors),
        "maximum_relative_error": max(relative_errors),
        "median_energy_recovery": statistics.median(energy_recoveries),
        "minimum_energy_recovery": min(energy_recoveries),
        "median_nonzero_recovery": statistics.median(
            float(row["parameter_step_nonzero_recovery"]) for row in rows
        ),
        "median_norm_ratio": statistics.median(
            float(row["parameter_step_norm_ratio"]) for row in rows
        ),
    }
    summary["passes"] = bool(
        summary["median_cosine"] >= PREFLIGHT_MINIMUM_MEDIAN_COSINE
        and summary["median_relative_error"] <= PREFLIGHT_MAXIMUM_MEDIAN_RELATIVE_ERROR
        and summary["median_energy_recovery"] >= PREFLIGHT_MINIMUM_MEDIAN_ENERGY_RECOVERY
        and summary["minimum_cosine"] >= PREFLIGHT_MINIMUM_ROW_COSINE
        and summary["maximum_relative_error"] <= PREFLIGHT_MAXIMUM_ROW_RELATIVE_ERROR
    )
    return summary


def _prepare(args: argparse.Namespace) -> None:
    from safetensors.torch import save_file

    gradient_dir = Path(args.source_gradient_dir).resolve()
    gradient_plan = _read_json(gradient_dir / "plan.json")
    gradient_report = _read_json(gradient_dir / "report.json")
    if gradient_plan.get("experiment_version") != GRADIENT_ALIGNMENT_VERSION:
        raise ValueError("batch intervention requires the current Gradient Projection plan")
    if gradient_report.get("plan_hash") != gradient_plan.get("plan_hash"):
        raise ValueError("batch intervention Gradient report failed plan replay")
    if gradient_report.get("blockers") != ["independent_distribution_intervention_not_run"]:
        raise ValueError("batch intervention cannot replace unrelated Gradient blockers")
    if gradient_plan.get("task_count") != 30 or gradient_plan.get("state_count") != 90:
        raise ValueError("batch intervention production validation requires 30x3 states")
    if not 0 < args.epsilon < 0.5:
        raise ValueError("batch intervention epsilon must lie in (0, 0.5)")
    learning_rates = tuple(float(value) for value in args.learning_rate_candidates)
    if (
        not learning_rates
        or any(value <= 0 or not math.isfinite(value) for value in learning_rates)
        or tuple(sorted(set(learning_rates))) != learning_rates
    ):
        raise ValueError("batch intervention learning-rate ladder must be unique and ascending")
    if not math.isclose(learning_rates[0], args.source_learning_rate, abs_tol=1e-15):
        raise ValueError("batch intervention ladder must begin at the source learning rate")

    output_dir = Path(args.output_dir).resolve()
    coordinate_dir = output_dir / "coordinate_gradients"
    coordinate_dir.mkdir(parents=True, exist_ok=True)
    jobs_by_task: defaultdict[str, list[dict[str, Any]]] = defaultdict(list)
    for job in gradient_plan["jobs"]:
        jobs_by_task[str(job["task_id"])].append(job)
    worker_rows = [
        row
        for path in sorted((gradient_dir / "workers").glob("partition_*.jsonl"))
        for row in _load_jsonl(path)
    ]
    worker_rows_by_job = {str(row["job_id"]): row for row in worker_rows}
    state_rows = {str(row["job_id"]): row for row in gradient_report["state_rows"]}
    if (
        len(worker_rows_by_job) != 90
        or len(state_rows) != 90
        or set(worker_rows_by_job) != set(state_rows)
        or any(
            not _valid_hashed_row(row, prefix="finance_contribution_gradient_result:")
            for row in worker_rows_by_job.values()
        )
        or any(
            state_rows[job_id].get("result_hash") != row.get("result_hash")
            for job_id, row in worker_rows_by_job.items()
        )
    ):
        raise ValueError("batch intervention state Gradient identities are incomplete")

    task_rows: list[dict[str, Any]] = []
    coordinate_artifacts: list[dict[str, Any]] = []
    for task_index, task_id in enumerate(sorted(jobs_by_task)):
        jobs = sorted(jobs_by_task[task_id], key=lambda row: str(row["state_id"]))
        if len(jobs) != STATE_COUNT_PER_TASK:
            raise ValueError("batch intervention requires exactly three states per task")
        rows = [state_rows[str(job["job_id"])] for job in jobs]
        probabilities = tuple(float(row["current_probability"]) for row in rows)
        if any(not math.isclose(value, 1.0 / 3.0, abs_tol=1e-12) for value in probabilities):
            raise ValueError("batch intervention v1 requires uniform three-state support")
        task_marginal = float(gradient_report["task_marginals"][task_id])
        gradients = tuple(
            _load_verified_gradient(
                Path(row["state_gradient_file"]),
                str(row["state_gradient_sha256"]),
            )
            for row in rows
        )
        coordinate_indices = []
        for basis_index, basis in enumerate(CONTRAST_BASIS):
            coordinate_index = len(coordinate_artifacts)
            coordinate_indices.append(coordinate_index)
            gradient = _linear_gradient_combination(
                gradients,
                tuple(task_marginal * value for value in basis),
            )
            path = coordinate_dir / f"coordinate_{coordinate_index:02d}.safetensors"
            save_file(gradient, path)
            coordinate_artifacts.append(
                {
                    "coordinate_index": coordinate_index,
                    "task_index": task_index,
                    "task_id": task_id,
                    "basis_index": basis_index,
                    "basis": list(basis),
                    "file": str(path),
                    "sha256": _sha256(path),
                    "gradient_norm": _gradient_norm(gradient),
                }
            )
            del gradient
        task_rows.append(
            {
                "task_index": task_index,
                "task_id": task_id,
                "task_type": jobs[0]["task_type"],
                "task_marginal": task_marginal,
                "probabilities": list(probabilities),
                "coordinate_indices": coordinate_indices,
                "states": [
                    {
                        "state_id": row["state_id"],
                        "strategy": row["strategy"],
                        "job_id": row["job_id"],
                        "estimation_conservative_centered_contribution": row[
                            "estimation_conservative_centered_contribution"
                        ],
                        "validation_conservative_centered_contribution": row[
                            "validation_conservative_centered_contribution"
                        ],
                        "estimation_centered_contribution": row[
                            "estimation_centered_contribution"
                        ],
                        "validation_centered_contribution": row[
                            "validation_centered_contribution"
                        ],
                    }
                    for row in rows
                ],
            }
        )
        del gradients
    if len(coordinate_artifacts) != 60:
        raise ValueError("batch intervention requires 60 centered contrast coordinates")

    hadamard = _sylvester_hadamard(HADAMARD_ORDER)
    design_rows: list[dict[str, Any]] = []
    for design_index, hadamard_row in enumerate(hadamard):
        signs = tuple(hadamard_row[: len(coordinate_artifacts)])
        minimum_probability = 1.0
        for task in task_rows:
            first, second = task["coordinate_indices"]
            weights = _contrast_weights(signs[first], signs[second])
            plus, minus = _symmetric_probabilities(
                tuple(task["probabilities"]),
                weights,
                epsilon=args.epsilon,
            )
            minimum_probability = min(minimum_probability, *plus, *minus)
        payload = {
            "design_row_index": design_index,
            "role": "orthogonal_design",
            "signs": list(signs),
            "minimum_conditional_probability": minimum_probability,
        }
        payload["row_id"] = canonical_hash(payload, prefix="finance_batch_design_row:")
        design_rows.append(payload)
    rows = list(design_rows)
    for replay_index, design_index in enumerate(NUMERIC_REPLAY_ROW_INDICES):
        source = design_rows[design_index]
        payload = {
            "design_row_index": design_index,
            "role": "numeric_replay",
            "replay_index": replay_index,
            "signs": source["signs"],
            "minimum_conditional_probability": source[
                "minimum_conditional_probability"
            ],
        }
        payload["row_id"] = canonical_hash(payload, prefix="finance_batch_design_row:")
        rows.append(payload)

    values: dict[str, Any] = {
        "experiment_version": BATCH_INTERVENTION_VERSION,
        "run_role": "mechanism_validation_then_production_gate",
        "source_gradient_plan_path": str(gradient_dir / "plan.json"),
        "source_gradient_plan_hash": gradient_plan["plan_hash"],
        "source_gradient_report_path": str(gradient_dir / "report.json"),
        "source_gradient_report_hash": gradient_report["report_hash"],
        "source_records_path": gradient_plan["source_records_path"],
        "source_records_sha256": gradient_plan["source_records_sha256"],
        "target_records_path": gradient_plan["target_records_path"],
        "target_records_sha256": gradient_plan["target_records_sha256"],
        "model_dir": gradient_plan["model_dir"],
        "base_model_manifest_hash": gradient_plan["base_model_manifest_hash"],
        "beneficiary_adapter_dir": gradient_plan["beneficiary_adapter_dir"],
        "beneficiary_adapter_tensor_sha256": gradient_plan[
            "beneficiary_adapter_tensor_sha256"
        ],
        "beneficiary_checkpoint_hash": gradient_plan["beneficiary_checkpoint_hash"],
        "beneficiary_model_state_id": gradient_plan["beneficiary_model_state_id"],
        "final_test_record_ids": gradient_plan["final_test_record_ids"],
        "final_test_set_id": gradient_plan["final_test_set_id"],
        "global_gradient_artifact": gradient_report["global_gradient_artifact"],
        "distribution_gradient_manifest_hash": gradient_report[
            "distribution_gradient_manifest_hash"
        ],
        "task_rows": task_rows,
        "coordinate_artifacts": coordinate_artifacts,
        "design_rows": rows,
        "orthogonal_design_row_count": HADAMARD_ORDER,
        "numeric_replay_row_indices": list(NUMERIC_REPLAY_ROW_INDICES),
        "task_count": len(task_rows),
        "state_count": sum(len(task["states"]) for task in task_rows),
        "coordinate_count": len(coordinate_artifacts),
        "epsilon": args.epsilon,
        "source_learning_rate": args.source_learning_rate,
        "learning_rate_candidates": list(learning_rates),
        "learning_rate_selection_policy": (
            "smallest_preregistered_rate_passing_parameter_fidelity_without_objective_access"
        ),
        "contrast_basis": [list(values) for values in CONTRAST_BASIS],
        "design": "64x60_sylvester_hadamard_zero_sum_task_contrasts",
        "intervention": "central_plus_minus_full_distribution_cached_gradient_step",
        "task_marginal_policy": gradient_report["task_marginal_policy"],
        "state_support_policy": "exactly_preserved_in_plus_and_minus_distributions",
        "compute_budget_policy": "one_cached_full_distribution_step_per_model",
        "preflight_thresholds": {
            "minimum_median_cosine": PREFLIGHT_MINIMUM_MEDIAN_COSINE,
            "maximum_median_relative_error": PREFLIGHT_MAXIMUM_MEDIAN_RELATIVE_ERROR,
            "minimum_median_energy_recovery": PREFLIGHT_MINIMUM_MEDIAN_ENERGY_RECOVERY,
            "minimum_row_cosine": PREFLIGHT_MINIMUM_ROW_COSINE,
            "maximum_row_relative_error": PREFLIGHT_MAXIMUM_ROW_RELATIVE_ERROR,
        },
        "maximum_reconstruction_relative_error": MAXIMUM_RECONSTRUCTION_RELATIVE_ERROR,
        "claim_boundary": (
            "The learning-rate ladder is selected only by exact float32 parameter-step "
            "fidelity before final-test evaluation. Batch outcomes cannot alter epsilon, "
            "design, thresholds, or the selected rate. Production promotion additionally "
            "requires source-scale matching and both independent rank gates."
        ),
    }
    values["plan_hash"] = canonical_hash(
        values,
        prefix="finance_batch_distribution_intervention_plan:",
    )
    output_dir.mkdir(parents=True, exist_ok=True)
    _write_json(output_dir / "plan.json", values)
    print(json.dumps(values, ensure_ascii=False, indent=2, sort_keys=True))


def _preflight(args: argparse.Namespace) -> None:
    os.environ["CUDA_VISIBLE_DEVICES"] = str(args.gpu_id)
    import torch
    from safetensors.torch import save_file

    output_dir = Path(args.output_dir).resolve()
    plan = _read_json(output_dir / "plan.json")
    if plan.get("experiment_version") != BATCH_INTERVENTION_VERSION:
        raise ValueError("batch intervention preflight requires a current plan")
    started = time.monotonic()
    _seed_everything(BATCH_INTERVENTION_NUMERIC_SEED)
    torch.cuda.reset_peak_memory_stats()
    model = _baseline_lora_model(
        Path(plan["model_dir"]),
        Path(plan["beneficiary_adapter_dir"]),
    )
    if _adapter_tensor_sha256(model) != plan["beneficiary_adapter_tensor_sha256"]:
        raise ValueError("batch intervention preflight loaded another Adapter")
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
        raise ValueError("batch intervention preflight parameter manifest changed")
    global_gradient_gpu = {
        name: value.to(
            device=initial_parameters[name].device,
            dtype=initial_parameters[name].dtype,
        )
        for name, value in global_gradient.items()
    }
    coordinate_gradients = tuple(
        {
            name: value.to(
                device=initial_parameters[name].device,
                dtype=initial_parameters[name].dtype,
            )
            for name, value in _load_verified_gradient(
                Path(artifact["file"]),
                str(artifact["sha256"]),
            ).items()
        }
        for artifact in plan["coordinate_artifacts"]
    )
    baselines = {}
    for learning_rate in plan["learning_rate_candidates"]:
        baseline = {name: value.detach().clone() for name, value in initial_parameters.items()}
        for name in baseline:
            baseline[name].add_(global_gradient_gpu[name], alpha=-float(learning_rate))
        baselines[str(learning_rate)] = baseline

    direction_dir = output_dir / "batch_directions"
    direction_dir.mkdir(parents=True, exist_ok=True)
    candidate_rows: dict[str, list[dict[str, Any]]] = {
        str(value): [] for value in plan["learning_rate_candidates"]
    }
    direction_artifacts = []
    for design_row in plan["design_rows"][: plan["orthogonal_design_row_count"]]:
        signs = tuple(int(value) for value in design_row["signs"])
        direction = _combine_coordinate_directions(coordinate_gradients, signs)
        path = direction_dir / f"direction_{design_row['design_row_index']:02d}.safetensors"
        cpu_direction = {
            name: value.detach().cpu().contiguous()
            for name, value in direction.items()
        }
        save_file(cpu_direction, path)
        direction_artifacts.append(
            {
                "design_row_index": design_row["design_row_index"],
                "row_id": design_row["row_id"],
                "file": str(path),
                "sha256": _sha256(path),
                "gradient_norm": _gradient_norm(direction),
            }
        )
        negative_direction = {name: -value for name, value in direction.items()}
        for learning_rate in plan["learning_rate_candidates"]:
            key = str(learning_rate)
            for sign_label, value in (("plus", direction), ("minus", negative_direction)):
                fidelity: dict[str, Any] = dict(
                    _parameter_step_fidelity(
                        initial_parameters,
                        baselines[key],
                        global_gradient_gpu,
                        value,
                        learning_rate=float(learning_rate),
                        directional_scale=float(plan["epsilon"]),
                    )
                )
                fidelity.update(
                    {
                        "design_row_index": design_row["design_row_index"],
                        "intervention_sign": sign_label,
                    }
                )
                candidate_rows[key].append(fidelity)
        del direction, negative_direction, cpu_direction

    candidate_summaries = []
    selected_learning_rate = None
    for learning_rate in plan["learning_rate_candidates"]:
        key = str(learning_rate)
        summary = _fidelity_summary(candidate_rows[key])
        summary["learning_rate"] = learning_rate
        candidate_summaries.append(summary)
        if selected_learning_rate is None and summary["passes"]:
            selected_learning_rate = float(learning_rate)
    production_scale_matched = bool(
        selected_learning_rate is not None
        and math.isclose(
            selected_learning_rate,
            float(plan["source_learning_rate"]),
            abs_tol=1e-15,
        )
    )
    report: dict[str, Any] = {
        "experiment_version": BATCH_INTERVENTION_VERSION,
        "plan_hash": plan["plan_hash"],
        "status": "passed" if selected_learning_rate is not None else "failed",
        "selected_learning_rate": selected_learning_rate,
        "source_learning_rate": plan["source_learning_rate"],
        "production_scale_matched": production_scale_matched,
        "candidate_summaries": candidate_summaries,
        "direction_artifacts": direction_artifacts,
        "direction_manifest_hash": canonical_hash(
            direction_artifacts,
            prefix="finance_batch_direction_manifest:",
        ),
        "runtime_seconds": time.monotonic() - started,
        "peak_gpu_memory_bytes": int(torch.cuda.max_memory_allocated()),
        "numeric_seed": BATCH_INTERVENTION_NUMERIC_SEED,
        "final_test_objective_accessed": False,
        "blockers": (
            [] if selected_learning_rate is not None else ["no_numerically_identifiable_rate"]
        ),
    }
    report["preflight_hash"] = canonical_hash(
        report,
        prefix="finance_batch_distribution_preflight:",
    )
    _write_json(output_dir / "preflight.json", report)
    print(json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True))
    del model, coordinate_gradients, global_gradient, global_gradient_gpu, baselines
    gc.collect()
    torch.cuda.empty_cache()


def _worker(args: argparse.Namespace) -> None:
    os.environ["CUDA_VISIBLE_DEVICES"] = str(args.gpu_id)
    import torch
    from peft import get_peft_model_state_dict

    output_dir = Path(args.output_dir).resolve()
    plan = _read_json(output_dir / "plan.json")
    preflight = _read_json(output_dir / "preflight.json")
    if preflight.get("plan_hash") != plan.get("plan_hash") or preflight.get("status") != "passed":
        raise ValueError("batch intervention worker requires a passing frozen preflight")
    if _sha256(Path(plan["source_records_path"])) != plan["source_records_sha256"]:
        raise ValueError("batch intervention source records changed")
    rows = [
        row
        for index, row in enumerate(plan["design_rows"])
        if index % args.partition_count == args.partition_index
    ]
    worker_path = output_dir / "workers" / f"partition_{args.partition_index}.jsonl"
    completed = {
        str(row["row_id"])
        for row in _load_jsonl(worker_path)
        if row.get("status") == "passed"
        and _valid_hashed_row(row, prefix="finance_batch_distribution_result:")
    }
    direction_artifacts = {
        int(row["design_row_index"]): row for row in preflight["direction_artifacts"]
    }
    source_records = _load_records(Path(plan["source_records_path"]))
    final_records = tuple(source_records[value] for value in plan["final_test_record_ids"])
    _seed_everything(BATCH_INTERVENTION_NUMERIC_SEED)
    torch.cuda.reset_peak_memory_stats()
    tokenizer = _load_tokenizer(Path(plan["model_dir"]))
    model = _baseline_lora_model(
        Path(plan["model_dir"]),
        Path(plan["beneficiary_adapter_dir"]),
    )
    if _adapter_tensor_sha256(model) != plan["beneficiary_adapter_tensor_sha256"]:
        raise ValueError("batch intervention worker loaded another Adapter")
    baseline_adapter_state = {
        name: tensor.detach().cpu().clone()
        for name, tensor in get_peft_model_state_dict(model).items()
    }
    global_artifact = plan["global_gradient_artifact"]
    global_gradient = _load_verified_gradient(
        Path(global_artifact["file"]),
        str(global_artifact["sha256"]),
    )
    learning_rate = float(preflight["selected_learning_rate"])
    _restore_adapter(model, baseline_adapter_state)
    _apply_gradient_step(model, global_gradient, learning_rate=learning_rate)
    baseline_performance, baseline_loss, baseline_tokens = _evaluate(
        model,
        tokenizer,
        final_records,
    )
    baseline_adapter_hash = _adapter_tensor_sha256(model)
    started = time.monotonic()
    completed_now = 0
    for row in rows:
        if str(row["row_id"]) in completed:
            continue
        artifact = direction_artifacts[int(row["design_row_index"])]
        direction = _load_verified_gradient(
            Path(artifact["file"]),
            str(artifact["sha256"]),
        )
        plus_gradient = {
            name: value.clone().add_(direction[name], alpha=float(plan["epsilon"]))
            for name, value in global_gradient.items()
        }
        minus_gradient = {
            name: value.clone().add_(direction[name], alpha=-float(plan["epsilon"]))
            for name, value in global_gradient.items()
        }
        _seed_everything(BATCH_INTERVENTION_NUMERIC_SEED)
        _restore_adapter(model, baseline_adapter_state)
        _apply_gradient_step(model, plus_gradient, learning_rate=learning_rate)
        plus_performance, plus_loss, plus_tokens = _evaluate(model, tokenizer, final_records)
        plus_adapter_hash = _adapter_tensor_sha256(model)
        _seed_everything(BATCH_INTERVENTION_NUMERIC_SEED)
        _restore_adapter(model, baseline_adapter_state)
        _apply_gradient_step(model, minus_gradient, learning_rate=learning_rate)
        minus_performance, minus_loss, minus_tokens = _evaluate(model, tokenizer, final_records)
        minus_adapter_hash = _adapter_tensor_sha256(model)
        if plus_tokens != baseline_tokens or minus_tokens != baseline_tokens:
            raise ValueError("batch intervention changed final-test token support")
        result: dict[str, Any] = {
            "experiment_version": BATCH_INTERVENTION_VERSION,
            "plan_hash": plan["plan_hash"],
            "preflight_hash": preflight["preflight_hash"],
            "row_id": row["row_id"],
            "design_row_index": row["design_row_index"],
            "role": row["role"],
            "replay_index": row.get("replay_index"),
            "partition_index": args.partition_index,
            "partition_count": args.partition_count,
            "gpu_id": args.gpu_id,
            "status": "passed",
            "epsilon": plan["epsilon"],
            "learning_rate": learning_rate,
            "baseline_performance": baseline_performance,
            "baseline_loss": baseline_loss,
            "plus_performance": plus_performance,
            "plus_loss": plus_loss,
            "minus_performance": minus_performance,
            "minus_loss": minus_loss,
            "central_directional_derivative": (
                (plus_performance - minus_performance) / (2.0 * float(plan["epsilon"]))
            ),
            "final_test_supervised_tokens": baseline_tokens,
            "baseline_adapter_tensor_sha256": baseline_adapter_hash,
            "plus_adapter_tensor_sha256": plus_adapter_hash,
            "minus_adapter_tensor_sha256": minus_adapter_hash,
            "direction_sha256": artifact["sha256"],
            "numeric_seed": BATCH_INTERVENTION_NUMERIC_SEED,
        }
        result["result_hash"] = canonical_hash(
            result,
            prefix="finance_batch_distribution_result:",
        )
        _append_jsonl(worker_path, result)
        completed_now += 1
        del direction, plus_gradient, minus_gradient
    worker_report = {
        "plan_hash": plan["plan_hash"],
        "preflight_hash": preflight["preflight_hash"],
        "partition_index": args.partition_index,
        "partition_count": args.partition_count,
        "gpu_id": args.gpu_id,
        "assigned_count": len(rows),
        "completed_now": completed_now,
        "runtime_seconds": time.monotonic() - started,
        "peak_gpu_memory_bytes": int(torch.cuda.max_memory_allocated()),
    }
    _write_json(
        output_dir / "workers" / f"partition_{args.partition_index}_report.json",
        worker_report,
    )
    print(json.dumps(worker_report, ensure_ascii=False, indent=2, sort_keys=True))
    del model, global_gradient, baseline_adapter_state
    gc.collect()
    torch.cuda.empty_cache()


def _aggregate(args: argparse.Namespace) -> None:
    output_dir = Path(args.output_dir).resolve()
    plan = _read_json(output_dir / "plan.json")
    preflight = _read_json(output_dir / "preflight.json")
    if preflight.get("plan_hash") != plan.get("plan_hash") or preflight.get("status") != "passed":
        raise ValueError("batch intervention aggregate requires a passing preflight")
    rows = [
        row
        for path in sorted((output_dir / "workers").glob("partition_*.jsonl"))
        for row in _load_jsonl(path)
    ]
    if len(rows) != len(plan["design_rows"]):
        raise ValueError("batch intervention matrix is incomplete")
    if any(
        not _valid_hashed_row(row, prefix="finance_batch_distribution_result:")
        for row in rows
    ):
        raise ValueError("batch intervention result identity failed replay")
    by_id = {str(row["row_id"]): row for row in rows}
    if len(by_id) != len(rows) or set(by_id) != {
        str(row["row_id"]) for row in plan["design_rows"]
    }:
        raise ValueError("batch intervention row support changed")
    ordered_design = [
        by_id[str(row["row_id"])]
        for row in plan["design_rows"]
        if row["role"] == "orthogonal_design"
    ]
    if len(ordered_design) != HADAMARD_ORDER:
        raise ValueError("batch intervention orthogonal design is incomplete")
    replay_ranges = []
    for design_index in plan["numeric_replay_row_indices"]:
        values = [
            float(row["central_directional_derivative"])
            for row in rows
            if int(row["design_row_index"]) == int(design_index)
        ]
        replay_ranges.append(max(values) - min(values))
    maximum_replay_range = max(replay_ranges)
    if maximum_replay_range != 0.0:
        raise ValueError("batch intervention numeric replay is not deterministic")

    hadamard = _sylvester_hadamard(HADAMARD_ORDER)
    observed = [float(row["central_directional_derivative"]) for row in ordered_design]
    coordinate_values = [
        sum(hadamard[row][column] * observed[row] for row in range(HADAMARD_ORDER))
        / HADAMARD_ORDER
        for column in range(plan["coordinate_count"])
    ]
    reconstructed_rows = [
        sum(
            hadamard[row][column] * coordinate_values[column]
            for column in range(plan["coordinate_count"])
        )
        for row in range(HADAMARD_ORDER)
    ]
    residual_norm = math.sqrt(
        sum(
            (actual - predicted) ** 2
            for actual, predicted in zip(observed, reconstructed_rows, strict=True)
        )
    )
    observed_norm = math.sqrt(sum(value * value for value in observed))
    reconstruction_relative_error = residual_norm / observed_norm if observed_norm else math.inf

    state_rows: list[dict[str, Any]] = []
    grouped: defaultdict[str, list[dict[str, Any]]] = defaultdict(list)
    for task in plan["task_rows"]:
        first, second = task["coordinate_indices"]
        recovered = _recover_centered_state_values(
            coordinate_values[first],
            coordinate_values[second],
            task_marginal=float(task["task_marginal"]),
        )
        for state, target in zip(task["states"], recovered, strict=True):
            row = {
                "task_id": task["task_id"],
                "task_type": task["task_type"],
                "state_id": state["state_id"],
                "strategy": state["strategy"],
                "recovered_centered_contribution": target,
                **{
                    key: state[key]
                    for key in (
                        "estimation_conservative_centered_contribution",
                        "validation_conservative_centered_contribution",
                        "estimation_centered_contribution",
                        "validation_centered_contribution",
                    )
                },
            }
            state_rows.append(row)
            grouped[str(task["task_id"])].append(row)
    estimation_rank = _rank_evidence(
        grouped,
        estimator_field="estimation_conservative_centered_contribution",
        target_field="recovered_centered_contribution",
        seed=BATCH_INTERVENTION_NUMERIC_SEED + 10,
    )
    validation_rank = _rank_evidence(
        grouped,
        estimator_field="validation_conservative_centered_contribution",
        target_field="recovered_centered_contribution",
        seed=BATCH_INTERVENTION_NUMERIC_SEED + 20,
    )

    task_by_index = {int(task["task_index"]): task for task in plan["task_rows"]}
    predicted_estimation = []
    predicted_validation = []
    for design_row in plan["design_rows"][:HADAMARD_ORDER]:
        signs = tuple(int(value) for value in design_row["signs"])
        row_predictions = {"estimation": 0.0, "validation": 0.0}
        for task in task_by_index.values():
            first, second = task["coordinate_indices"]
            weights = _contrast_weights(signs[first], signs[second])
            for label, field in (
                ("estimation", "estimation_conservative_centered_contribution"),
                ("validation", "validation_conservative_centered_contribution"),
            ):
                row_predictions[label] += float(task["task_marginal"]) * sum(
                    weight * float(state[field])
                    for weight, state in zip(weights, task["states"], strict=True)
                )
        predicted_estimation.append(row_predictions["estimation"])
        predicted_validation.append(row_predictions["validation"])
    mechanism_supported = bool(
        estimation_rank["passes_rank_gate"]
        and validation_rank["passes_rank_gate"]
        and reconstruction_relative_error <= plan["maximum_reconstruction_relative_error"]
        and maximum_replay_range == 0.0
    )
    production_authorized = bool(
        mechanism_supported and preflight["production_scale_matched"]
    )
    blockers = []
    if not estimation_rank["passes_rank_gate"]:
        blockers.append("estimation_rank_gate_failed")
    if not validation_rank["passes_rank_gate"]:
        blockers.append("validation_rank_gate_failed")
    if reconstruction_relative_error > plan["maximum_reconstruction_relative_error"]:
        blockers.append("batch_linear_reconstruction_failed")
    if not preflight["production_scale_matched"]:
        blockers.append("numeric_preflight_selected_nonproduction_learning_rate")
    report: dict[str, Any] = {
        "experiment_version": BATCH_INTERVENTION_VERSION,
        "plan_hash": plan["plan_hash"],
        "preflight_hash": preflight["preflight_hash"],
        "source_gradient_report_hash": plan["source_gradient_report_hash"],
        "status": "passed" if mechanism_supported else "failed",
        "mechanism_supported": mechanism_supported,
        "production_authorized": production_authorized,
        "selected_learning_rate": preflight["selected_learning_rate"],
        "production_scale_matched": preflight["production_scale_matched"],
        "epsilon": plan["epsilon"],
        "task_count": plan["task_count"],
        "state_count": plan["state_count"],
        "orthogonal_design_row_count": HADAMARD_ORDER,
        "numeric_replay_count": len(NUMERIC_REPLAY_ROW_INDICES),
        "maximum_numeric_replay_range": maximum_replay_range,
        "reconstruction_relative_error": reconstruction_relative_error,
        "estimation_rank_evidence": estimation_rank,
        "validation_rank_evidence": validation_rank,
        "row_level_estimation_pearson": _pearson(predicted_estimation, observed),
        "row_level_validation_pearson": _pearson(predicted_validation, observed),
        "baseline_loss": statistics.fmean(float(row["baseline_loss"]) for row in rows),
        "baseline_performance": statistics.fmean(
            float(row["baseline_performance"]) for row in rows
        ),
        "final_test_supervised_tokens": int(rows[0]["final_test_supervised_tokens"]),
        "blockers": blockers,
        "state_rows": state_rows,
        "coordinate_values": coordinate_values,
        "claim_boundary": (
            "This report validates Scheme 3 against a preregistered central batch "
            "distribution perturbation. It may authorize production only at the original "
            "learning-rate scale; a larger fidelity-selected rate is mechanism evidence only."
        ),
    }
    report["report_hash"] = canonical_hash(
        report,
        prefix="finance_batch_distribution_intervention_report:",
    )
    _write_json(output_dir / "report.json", report)
    print(json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True))


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Validate Scheme 3 with a numeric-identifiable batch symmetric intervention"
    )
    subparsers = parser.add_subparsers(dest="command", required=True)
    prepare = subparsers.add_parser("prepare")
    prepare.add_argument("--source-gradient-dir", required=True)
    prepare.add_argument("--output-dir", required=True)
    prepare.add_argument("--epsilon", type=float, default=DEFAULT_EPSILON)
    prepare.add_argument("--source-learning-rate", type=float, default=5e-5)
    prepare.add_argument(
        "--learning-rate-candidates",
        type=float,
        nargs="+",
        default=list(DEFAULT_LEARNING_RATE_CANDIDATES),
    )
    preflight = subparsers.add_parser("preflight")
    preflight.add_argument("--output-dir", required=True)
    preflight.add_argument("--gpu-id", type=int, default=0)
    worker = subparsers.add_parser("worker")
    worker.add_argument("--output-dir", required=True)
    worker.add_argument("--gpu-id", type=int, required=True)
    worker.add_argument("--partition-index", type=int, required=True)
    worker.add_argument("--partition-count", type=int, required=True)
    aggregate = subparsers.add_parser("aggregate")
    aggregate.add_argument("--output-dir", required=True)
    return parser


def main() -> None:
    args = _parser().parse_args()
    if args.command == "prepare":
        _prepare(args)
    elif args.command == "preflight":
        _preflight(args)
    elif args.command == "worker":
        _worker(args)
    else:
        _aggregate(args)


if __name__ == "__main__":
    main()
