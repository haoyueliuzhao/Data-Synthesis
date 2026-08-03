from __future__ import annotations

import argparse
import gc
import json
import math
import multiprocessing
import os
import statistics
import time
from collections import defaultdict
from concurrent.futures import ProcessPoolExecutor, as_completed
from pathlib import Path
from typing import Any

from trusted_synthesis.experiments.vtdo_experiment.contribution_validation import (
    _cluster_bootstrap_interval,
    _spearman,
)
from trusted_synthesis.experiments.vtdo_experiment.phase1_contribution_gradient import (
    GRADIENT_ALIGNMENT_VERSION,
    PRODUCTION_MINIMUM_TASK_COUNT,
    _current_state_probabilities,
    _gradient_parameter_manifest,
    _load_jsonl,
    _load_verified_gradient,
    _pairwise_concordance,
    _permutation_p_value,
    _sha256,
    _valid_hashed_row,
    _winner,
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

DISTRIBUTION_INTERVENTION_VERSION = "finance_distribution_intervention.v1"
RUN_ROLES = ("smoke", "production_validation")
PRODUCTION_MINIMUM_INTERVENTION_SEEDS = 4
NUMERIC_REPLAY_TOLERANCE = 1e-6


def _append_jsonl(path: Path, value: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as sink:
        sink.write(json.dumps(value, ensure_ascii=False, sort_keys=True) + "\n")
        sink.flush()
        os.fsync(sink.fileno())


def _perturbed_distribution(
    probabilities: dict[str, float],
    *,
    target_state_id: str,
    epsilon: float,
) -> dict[str, float]:
    if target_state_id not in probabilities:
        raise ValueError("distribution intervention target is outside pi_t")
    if not 0 < epsilon < 0.5:
        raise ValueError("distribution intervention epsilon must lie in (0, 0.5)")
    if any(value <= 0 or not math.isfinite(value) for value in probabilities.values()):
        raise ValueError("distribution intervention requires positive finite pi_t")
    if not math.isclose(sum(probabilities.values()), 1.0, abs_tol=1e-12):
        raise ValueError("distribution intervention pi_t must sum to one")
    result = {
        state_id: (1.0 - epsilon) * probability + (epsilon if state_id == target_state_id else 0.0)
        for state_id, probability in probabilities.items()
    }
    if set(result) != set(probabilities):
        raise ValueError("distribution intervention changed state support")
    if not math.isclose(sum(result.values()), 1.0, abs_tol=1e-12):
        raise ValueError("distribution intervention failed mass conservation")
    if any(value <= 0 for value in result.values()):
        raise ValueError("distribution intervention removed accepted support")
    return result


def _conditional_distribution_gradient(
    global_gradient: dict[str, Any],
    task_gradient: dict[str, Any],
    state_gradient: dict[str, Any],
    *,
    task_marginal: float,
    epsilon: float,
) -> dict[str, Any]:
    if not 0 < task_marginal <= 1 or not math.isfinite(task_marginal):
        raise ValueError("distribution intervention requires a valid task marginal")
    if not 0 < epsilon < 0.5:
        raise ValueError("distribution intervention epsilon must lie in (0, 0.5)")
    names = tuple(global_gradient)
    if tuple(task_gradient) != names or tuple(state_gradient) != names:
        raise ValueError("distribution gradient parameter manifests do not align")
    result = {}
    for name in names:
        if (
            global_gradient[name].shape != task_gradient[name].shape
            or global_gradient[name].shape != state_gradient[name].shape
        ):
            raise ValueError("distribution gradient tensor shapes do not align")
        value = global_gradient[name].clone()
        value.add_(
            state_gradient[name] - task_gradient[name],
            alpha=task_marginal * epsilon,
        )
        result[name] = value.contiguous()
    return result


def _apply_gradient_step(
    model: Any,
    gradients: dict[str, Any],
    *,
    learning_rate: float,
) -> None:
    import torch

    if learning_rate <= 0 or not math.isfinite(learning_rate):
        raise ValueError("distribution intervention learning rate must be positive")
    parameters = {
        name: parameter
        for name, parameter in sorted(model.named_parameters())
        if parameter.requires_grad
    }
    if not parameters or tuple(parameters) != tuple(gradients):
        raise ValueError("distribution intervention parameter space changed")
    with torch.no_grad():
        for name, parameter in parameters.items():
            gradient = gradients[name]
            if gradient.shape != parameter.shape or not torch.isfinite(gradient).all():
                raise ValueError(f"invalid frozen distribution gradient:{name}")
            parameter.add_(
                gradient.to(device=parameter.device, dtype=parameter.dtype),
                alpha=-learning_rate,
            )
    if any(not torch.isfinite(parameter).all() for parameter in parameters.values()):
        raise ValueError("distribution intervention produced non-finite parameters")


def _gradient_artifact_map(
    rows: list[dict[str, Any]],
    *,
    key: str,
) -> dict[str, dict[str, Any]]:
    values = {str(row[key]): row for row in rows}
    if len(values) != len(rows):
        raise ValueError(f"duplicate frozen gradient artifact:{key}")
    if not values:
        raise ValueError("distribution intervention has no frozen gradients")
    return values


def _restore_adapter(model: Any, baseline_state: dict[str, Any]) -> None:
    from peft import set_peft_model_state_dict

    result = set_peft_model_state_dict(model, baseline_state, adapter_name="default")
    if getattr(result, "unexpected_keys", ()):
        raise ValueError("distribution intervention restore produced unexpected Adapter keys")


def _rank_evidence(
    grouped: dict[str, list[dict[str, Any]]],
    *,
    estimator_field: str,
    target_field: str,
    seed: int,
) -> dict[str, Any]:
    task_rows: list[dict[str, Any]] = []
    vectors: list[tuple[list[float], list[float]]] = []
    for task_id, values in sorted(grouped.items()):
        ordered = sorted(values, key=lambda row: str(row["state_id"]))
        estimator = [float(row[estimator_field]) for row in ordered]
        target = [float(row[target_field]) for row in ordered]
        state_ids = [str(row["state_id"]) for row in ordered]
        task_rows.append(
            {
                "task_id": task_id,
                "spearman": _spearman(estimator, target),
                "pairwise_concordance": _pairwise_concordance(estimator, target),
                "winner_agreement": float(
                    _winner(estimator, state_ids) == _winner(target, state_ids)
                ),
            }
        )
        vectors.append((estimator, target))
    spearman = [float(row["spearman"]) for row in task_rows]
    concordance = [float(row["pairwise_concordance"]) for row in task_rows]
    winners = [float(row["winner_agreement"]) for row in task_rows]
    evidence: dict[str, Any] = {
        "estimator_field": estimator_field,
        "target_field": target_field,
        "task_count": len(task_rows),
        "macro_task_spearman": statistics.fmean(spearman),
        "macro_task_spearman_ci95": _cluster_bootstrap_interval(
            spearman,
            samples=5000,
            seed=seed,
        ),
        "macro_pairwise_concordance": statistics.fmean(concordance),
        "macro_pairwise_concordance_ci95": _cluster_bootstrap_interval(
            concordance,
            samples=5000,
            seed=seed + 1,
        ),
        "winner_agreement_rate": statistics.fmean(winners),
        "macro_spearman_p_value": _permutation_p_value(
            vectors,
            statistic="spearman",
            iterations=10000,
            seed=seed + 2,
        ),
        "macro_pairwise_concordance_p_value": _permutation_p_value(
            vectors,
            statistic="concordance",
            iterations=10000,
            seed=seed + 3,
        ),
        "task_rows": task_rows,
    }
    evidence["passes_rank_gate"] = bool(
        evidence["macro_task_spearman_ci95"][0] > 0
        and evidence["macro_pairwise_concordance_ci95"][0] > 0.5
        and evidence["winner_agreement_rate"] >= 0.5
        and evidence["macro_spearman_p_value"] < 0.05
        and evidence["macro_pairwise_concordance_p_value"] < 0.05
    )
    return evidence


def prepare(args: argparse.Namespace) -> None:
    gradient_dir = Path(args.source_gradient_dir).resolve()
    gradient_plan = _read_json(gradient_dir / "plan.json")
    gradient_report = _read_json(gradient_dir / "report.json")
    gradient_manifest = _read_json(gradient_dir / "evaluation_gradient_manifest.json")
    if gradient_plan.get("experiment_version") != GRADIENT_ALIGNMENT_VERSION:
        raise ValueError("distribution intervention requires a current Gradient Projection plan")
    if gradient_report.get("plan_hash") != gradient_plan.get("plan_hash"):
        raise ValueError("Gradient Projection report does not replay its plan")
    if gradient_manifest.get("plan_hash") != gradient_plan.get("plan_hash"):
        raise ValueError("Gradient Projection manifest does not replay its plan")
    if args.run_role not in RUN_ROLES:
        raise ValueError("unknown distribution intervention run role")
    if not 0 < args.epsilon < 0.5:
        raise ValueError("distribution intervention epsilon must lie in (0, 0.5)")
    if args.step_count != 1:
        raise ValueError("exact cached-gradient distribution intervention requires one step")
    seeds = tuple(args.intervention_seeds)
    if len(seeds) != len(set(seeds)):
        raise ValueError("distribution intervention seeds must be unique")
    if args.run_role == "production_validation":
        if gradient_plan["task_count"] < PRODUCTION_MINIMUM_TASK_COUNT:
            raise ValueError("production distribution validation requires at least 30 tasks")
        if len(seeds) < PRODUCTION_MINIMUM_INTERVENTION_SEEDS:
            raise ValueError("production distribution validation requires at least four seeds")
    required_gradient_fields = {
        "task_marginal_policy",
        "task_marginals",
        "task_gradient_artifacts",
        "global_gradient_artifact",
        "distribution_gradient_manifest_hash",
    }
    if not required_gradient_fields.issubset(gradient_report):
        raise ValueError("Gradient Projection report lacks full-distribution artifacts")
    if gradient_report["task_marginal_policy"] != "uniform_over_selected_tasks":
        raise ValueError("unsupported task marginal policy")
    task_marginals = {
        str(task_id): float(value) for task_id, value in gradient_report["task_marginals"].items()
    }
    if any(value <= 0 for value in task_marginals.values()) or not math.isclose(
        sum(task_marginals.values()), 1.0, abs_tol=1e-12
    ):
        raise ValueError("Gradient Projection task marginals are invalid")
    jobs_by_task: defaultdict[str, list[dict[str, Any]]] = defaultdict(list)
    for job in gradient_plan["jobs"]:
        jobs_by_task[str(job["task_id"])].append(job)
    task_jobs = []
    for task_id, states in sorted(jobs_by_task.items()):
        states.sort(key=lambda row: str(row["state_id"]))
        probabilities = _current_state_probabilities([str(row["state_id"]) for row in states])
        task_jobs.append(
            {
                "task_id": task_id,
                "task_type": states[0]["task_type"],
                "states": states,
                "current_probabilities": probabilities,
            }
        )
    task_ids = {str(job["task_id"]) for job in task_jobs}
    if task_ids != set(task_marginals):
        raise ValueError("task marginals do not cover the Gradient Projection population")
    output_dir = Path(args.output_dir).resolve()
    output_dir.mkdir(parents=True, exist_ok=True)
    values: dict[str, Any] = {
        "experiment_version": DISTRIBUTION_INTERVENTION_VERSION,
        "run_role": args.run_role,
        "source_gradient_plan_path": str(gradient_dir / "plan.json"),
        "source_gradient_plan_hash": gradient_plan["plan_hash"],
        "source_gradient_report_path": str(gradient_dir / "report.json"),
        "source_gradient_report_hash": gradient_report["report_hash"],
        "source_gradient_manifest_path": str(gradient_dir / "evaluation_gradient_manifest.json"),
        "source_gradient_manifest_hash": gradient_manifest["manifest_hash"],
        "source_records_path": gradient_plan["source_records_path"],
        "source_records_sha256": gradient_plan["source_records_sha256"],
        "target_records_path": gradient_plan["target_records_path"],
        "target_records_sha256": gradient_plan["target_records_sha256"],
        "model_dir": gradient_plan["model_dir"],
        "base_model_manifest_hash": gradient_plan["base_model_manifest_hash"],
        "beneficiary_adapter_dir": gradient_plan["beneficiary_adapter_dir"],
        "beneficiary_adapter_tensor_sha256": gradient_plan["beneficiary_adapter_tensor_sha256"],
        "beneficiary_model_state_id": gradient_plan["beneficiary_model_state_id"],
        "beneficiary_checkpoint_hash": gradient_plan["beneficiary_checkpoint_hash"],
        "final_test_record_ids": gradient_plan["final_test_record_ids"],
        "final_test_set_id": gradient_plan["final_test_set_id"],
        "gradient_parameter_manifest_hash": gradient_manifest["parameter_manifest_hash"],
        "distribution_gradient_manifest_hash": gradient_report[
            "distribution_gradient_manifest_hash"
        ],
        "global_gradient_artifact": gradient_report["global_gradient_artifact"],
        "task_gradient_artifacts": gradient_report["task_gradient_artifacts"],
        "state_gradient_artifacts": gradient_report["state_rows"],
        "task_jobs": task_jobs,
        "task_count": len(task_jobs),
        "state_count": sum(len(job["states"]) for job in task_jobs),
        "task_marginal_policy": gradient_report["task_marginal_policy"],
        "task_marginals": task_marginals,
        "intervention_seeds": seeds,
        "intervention_seed_role": "numeric_replay_only_not_independent_estimand",
        "epsilon": args.epsilon,
        "step_count": args.step_count,
        "learning_rate": args.learning_rate,
        "optimizer": "exact_cached_full_distribution_gradient_sgd",
        "optimizer_state_policy": "one_stateless_sgd_step_from_frozen_checkpoint",
        "distribution_formula": "pi_prime_x=(1-epsilon)*pi_x+epsilon*delta_z",
        "state_support_policy": "exactly_preserved",
        "compute_budget_policy": "one_full_distribution_gradient_application_per_model",
        "evaluation_role": "untouched_final_test",
        "claim_boundary": (
            "This finite full-distribution perturbation preserves the task marginal and is used "
            "only as an independent final-test target for Gradient Projection. Numeric replay "
            "seeds test reproducibility and are not counted as independent statistical samples."
        ),
    }
    values["intervention_estimand_id"] = canonical_hash(
        {
            "beneficiary_checkpoint_hash": values["beneficiary_checkpoint_hash"],
            "final_test_set_id": values["final_test_set_id"],
            "epsilon": values["epsilon"],
            "step_count": values["step_count"],
            "learning_rate": values["learning_rate"],
            "optimizer": values["optimizer"],
            "distribution_formula": values["distribution_formula"],
            "compute_budget_policy": values["compute_budget_policy"],
            "task_marginal_policy": values["task_marginal_policy"],
            "distribution_gradient_manifest_hash": values["distribution_gradient_manifest_hash"],
        },
        prefix="finance_distribution_intervention_estimand:",
    )
    values["plan_hash"] = canonical_hash(
        values,
        prefix="finance_distribution_intervention_plan:",
    )
    _write_json(output_dir / "plan.json", values)
    print(json.dumps(values, ensure_ascii=False, indent=2, sort_keys=True))


def _worker(
    plan_path: str,
    *,
    gpu_id: int,
    seed: int,
    partition_index: int,
    partition_count: int,
) -> dict[str, Any]:
    os.environ["CUDA_VISIBLE_DEVICES"] = str(gpu_id)
    import torch
    from peft import get_peft_model_state_dict

    plan = _read_json(Path(plan_path))
    if plan.get("experiment_version") != DISTRIBUTION_INTERVENTION_VERSION:
        raise ValueError("distribution intervention worker requires a current plan")
    if _sha256(Path(plan["source_records_path"])) != plan["source_records_sha256"]:
        raise ValueError("final-test records changed after intervention planning")
    if _sha256(Path(plan["target_records_path"])) != plan["target_records_sha256"]:
        raise ValueError("target records changed after intervention planning")
    output_dir = Path(plan_path).parent
    worker_path = output_dir / "workers" / f"seed_{seed}_partition_{partition_index}.jsonl"
    completed = set()
    for row in _load_jsonl(worker_path):
        if row.get("status") != "passed":
            continue
        if not _valid_hashed_row(
            row,
            prefix="finance_distribution_intervention_result:",
        ):
            raise ValueError("distribution intervention resume identity failed replay")
        completed.add((str(row["task_id"]), str(row["state_id"])))
    task_jobs = [
        job
        for index, job in enumerate(plan["task_jobs"])
        if index % partition_count == partition_index
    ]
    source_records = _load_records(Path(plan["source_records_path"]))
    final_records = tuple(source_records[record_id] for record_id in plan["final_test_record_ids"])
    _seed_everything(seed)
    torch.cuda.reset_peak_memory_stats()
    tokenizer = _load_tokenizer(Path(plan["model_dir"]))
    model = _baseline_lora_model(
        Path(plan["model_dir"]),
        Path(plan["beneficiary_adapter_dir"]),
    )
    if _adapter_tensor_sha256(model) != plan["beneficiary_adapter_tensor_sha256"]:
        raise ValueError("distribution intervention loaded another beneficiary Adapter")
    baseline_adapter_state = {
        name: tensor.detach().cpu().clone()
        for name, tensor in get_peft_model_state_dict(model).items()
    }
    parameter_manifest, parameter_manifest_hash = _gradient_parameter_manifest(model)
    if parameter_manifest_hash != plan["gradient_parameter_manifest_hash"]:
        raise ValueError("distribution intervention parameter space changed")
    del parameter_manifest
    global_artifact = plan["global_gradient_artifact"]
    global_gradient = _load_verified_gradient(
        Path(global_artifact["file"]),
        str(global_artifact["sha256"]),
    )
    task_artifacts = _gradient_artifact_map(
        plan["task_gradient_artifacts"],
        key="task_id",
    )
    state_artifacts = _gradient_artifact_map(
        plan["state_gradient_artifacts"],
        key="job_id",
    )
    _restore_adapter(model, baseline_adapter_state)
    if _adapter_tensor_sha256(model) != plan["beneficiary_adapter_tensor_sha256"]:
        raise ValueError("distribution intervention failed baseline Adapter replay")
    _apply_gradient_step(
        model,
        global_gradient,
        learning_rate=float(plan["learning_rate"]),
    )
    baseline_performance, baseline_loss, baseline_tokens = _evaluate(
        model,
        tokenizer,
        final_records,
    )
    baseline_adapter_hash = _adapter_tensor_sha256(model)
    completed_now = 0
    started = time.monotonic()
    for task in task_jobs:
        states = tuple(task["states"])
        probabilities = {
            str(state_id): float(value) for state_id, value in task["current_probabilities"].items()
        }
        task_id = str(task["task_id"])
        task_artifact = task_artifacts[task_id]
        task_gradient = _load_verified_gradient(
            Path(task_artifact["file"]),
            str(task_artifact["sha256"]),
        )
        for state in states:
            state_id = str(state["state_id"])
            if (task_id, state_id) in completed:
                continue
            state_artifact = state_artifacts[str(state["job_id"])]
            state_gradient = _load_verified_gradient(
                Path(state_artifact["state_gradient_file"]),
                str(state_artifact["state_gradient_sha256"]),
            )
            perturbed = _perturbed_distribution(
                probabilities,
                target_state_id=state_id,
                epsilon=float(plan["epsilon"]),
            )
            task_marginal = float(plan["task_marginals"][task_id])
            perturbed_gradient = _conditional_distribution_gradient(
                global_gradient,
                task_gradient,
                state_gradient,
                task_marginal=task_marginal,
                epsilon=float(plan["epsilon"]),
            )
            _seed_everything(seed)
            _restore_adapter(model, baseline_adapter_state)
            if _adapter_tensor_sha256(model) != plan["beneficiary_adapter_tensor_sha256"]:
                raise ValueError("distribution intervention failed Adapter restore")
            _apply_gradient_step(
                model,
                perturbed_gradient,
                learning_rate=float(plan["learning_rate"]),
            )
            perturbed_performance, perturbed_loss, perturbed_tokens = _evaluate(
                model,
                tokenizer,
                final_records,
            )
            if perturbed_tokens != baseline_tokens:
                raise ValueError("distribution intervention changed final-test token support")
            performance_gain = perturbed_performance - baseline_performance
            directional_scale = task_marginal * float(plan["epsilon"])
            result = {
                "experiment_version": DISTRIBUTION_INTERVENTION_VERSION,
                "plan_hash": plan["plan_hash"],
                "task_id": task["task_id"],
                "task_type": task["task_type"],
                "state_id": state_id,
                "strategy": state["strategy"],
                "record_id": state["record_id"],
                "seed": seed,
                "gpu_id": gpu_id,
                "partition_index": partition_index,
                "partition_count": partition_count,
                "status": "passed",
                "current_probabilities": probabilities,
                "perturbed_probabilities": perturbed,
                "target_probability_before": probabilities[state_id],
                "target_probability_after": perturbed[state_id],
                "effective_target_mass_shift": (perturbed[state_id] - probabilities[state_id]),
                "epsilon": plan["epsilon"],
                "step_count": plan["step_count"],
                "task_marginal": task_marginal,
                "directional_scale": directional_scale,
                "distribution_gradient_manifest_hash": plan["distribution_gradient_manifest_hash"],
                "baseline_performance": baseline_performance,
                "baseline_loss": baseline_loss,
                "perturbed_performance": perturbed_performance,
                "perturbed_loss": perturbed_loss,
                "performance_gain": performance_gain,
                "finite_difference_contribution": performance_gain / directional_scale,
                "final_test_supervised_tokens": baseline_tokens,
                "baseline_adapter_tensor_sha256": baseline_adapter_hash,
                "perturbed_adapter_tensor_sha256": _adapter_tensor_sha256(model),
                "cached_gradient_policy": "exact_at_frozen_beneficiary_checkpoint",
                "baseline_compute_units": 1,
                "perturbed_compute_units": 1,
            }
            result["result_hash"] = canonical_hash(
                result,
                prefix="finance_distribution_intervention_result:",
            )
            _append_jsonl(worker_path, result)
            completed_now += 1
            del state_gradient, perturbed_gradient
        del task_gradient
    report = {
        "seed": seed,
        "gpu_id": gpu_id,
        "partition_index": partition_index,
        "partition_count": partition_count,
        "task_count": len(task_jobs),
        "completed_before_resume": len(completed),
        "completed_now": completed_now,
        "runtime_seconds": time.monotonic() - started,
        "peak_gpu_memory_bytes": int(torch.cuda.max_memory_allocated()),
    }
    del model, baseline_adapter_state, global_gradient
    gc.collect()
    torch.cuda.empty_cache()
    return report


def run(args: argparse.Namespace) -> None:
    output_dir = Path(args.output_dir).resolve()
    plan_path = output_dir / "plan.json"
    plan = _read_json(plan_path)
    if not args.gpu_ids or len(set(args.gpu_ids)) != len(args.gpu_ids):
        raise ValueError("distribution intervention requires unique GPU ids")
    if args.partitions_per_seed < 1:
        raise ValueError("partitions_per_seed must be positive")
    specs = [
        (seed, partition)
        for seed in plan["intervention_seeds"]
        for partition in range(args.partitions_per_seed)
    ]
    context = multiprocessing.get_context("spawn")
    reports = []
    for start in range(0, len(specs), len(args.gpu_ids)):
        wave = specs[start : start + len(args.gpu_ids)]
        with ProcessPoolExecutor(max_workers=len(wave), mp_context=context) as executor:
            futures = {
                executor.submit(
                    _worker,
                    str(plan_path),
                    gpu_id=gpu_id,
                    seed=int(seed),
                    partition_index=partition,
                    partition_count=args.partitions_per_seed,
                ): (gpu_id, seed, partition)
                for gpu_id, (seed, partition) in zip(
                    args.gpu_ids,
                    wave,
                    strict=False,
                )
            }
            for future in as_completed(futures):
                reports.append(future.result())
    summary = {
        "plan_hash": plan["plan_hash"],
        "workers": sorted(
            reports,
            key=lambda row: (row["seed"], row["partition_index"]),
        ),
    }
    _write_json(output_dir / "worker_summary.json", summary)
    print(json.dumps(summary, ensure_ascii=False, indent=2, sort_keys=True))


def aggregate(args: argparse.Namespace) -> None:
    output_dir = Path(args.output_dir).resolve()
    plan = _read_json(output_dir / "plan.json")
    gradient_report = _read_json(Path(plan["source_gradient_report_path"]))
    if gradient_report.get("report_hash") != plan["source_gradient_report_hash"]:
        raise ValueError("Gradient Projection report changed after intervention planning")
    rows = [
        row
        for path in sorted((output_dir / "workers").glob("*.jsonl"))
        for row in _load_jsonl(path)
    ]
    expected = int(plan["state_count"]) * len(plan["intervention_seeds"])
    if len(rows) != expected:
        raise ValueError(
            f"distribution intervention matrix is incomplete:{len(rows)} != {expected}"
        )
    if {row["plan_hash"] for row in rows} != {plan["plan_hash"]}:
        raise ValueError("distribution intervention rows cross plans")
    if any(
        not _valid_hashed_row(row, prefix="finance_distribution_intervention_result:")
        for row in rows
    ):
        raise ValueError("distribution intervention result identity failed replay")
    by_atomic_key = {
        (str(row["task_id"]), str(row["state_id"]), int(row["seed"])): row for row in rows
    }
    if len(by_atomic_key) != len(rows):
        raise ValueError("distribution intervention contains duplicate atomic observations")
    if any(row["baseline_compute_units"] != row["perturbed_compute_units"] for row in rows):
        raise ValueError("distribution intervention violated the fixed compute budget")
    gradient_by_key = {
        (str(row["task_id"]), str(row["state_id"])): row for row in gradient_report["state_rows"]
    }
    intervention_values: defaultdict[tuple[str, str], list[float]] = defaultdict(list)
    intervention_gains: defaultdict[tuple[str, str], list[float]] = defaultdict(list)
    representatives = {}
    for row in rows:
        key = (str(row["task_id"]), str(row["state_id"]))
        intervention_gains[key].append(float(row["performance_gain"]))
        intervention_values[key].append(float(row["finite_difference_contribution"]))
        representatives[key] = row
    if set(intervention_values) != set(gradient_by_key):
        raise ValueError("distribution intervention and Gradient Projection supports differ")
    state_rows = []
    replay_ranges = []
    for key, values in sorted(intervention_values.items()):
        gains = intervention_gains[key]
        gradient = gradient_by_key[key]
        representative = representatives[key]
        replay_range = max(values) - min(values)
        replay_ranges.append(replay_range)
        state_rows.append(
            {
                "task_id": key[0],
                "task_type": representative["task_type"],
                "state_id": key[1],
                "strategy": representative["strategy"],
                "gradient_estimation_centered": gradient["estimation_centered_contribution"],
                "gradient_estimation_conservative_centered": gradient[
                    "estimation_conservative_centered_contribution"
                ],
                "gradient_validation_centered": gradient["validation_centered_contribution"],
                "gradient_validation_conservative_centered": gradient[
                    "validation_conservative_centered_contribution"
                ],
                "intervention_mean_gain": statistics.fmean(gains),
                "intervention_mean_contribution": statistics.fmean(values),
                "intervention_seed_gains": gains,
                "intervention_numeric_replays": values,
                "numeric_replay_range": replay_range,
            }
        )
    grouped: defaultdict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in state_rows:
        grouped[str(row["task_id"])].append(row)
    estimation_evidence = _rank_evidence(
        grouped,
        estimator_field="gradient_estimation_conservative_centered",
        target_field="intervention_mean_contribution",
        seed=20260861,
    )
    validation_evidence = _rank_evidence(
        grouped,
        estimator_field="gradient_validation_conservative_centered",
        target_field="intervention_mean_contribution",
        seed=20260871,
    )
    raw_estimation_evidence = _rank_evidence(
        grouped,
        estimator_field="gradient_estimation_centered",
        target_field="intervention_mean_contribution",
        seed=20260881,
    )
    cross_evaluation_passed = bool(
        gradient_report["macro_task_spearman_ci95"][0] > 0
        and gradient_report["macro_pairwise_concordance_ci95"][0] > 0.5
        and gradient_report["winner_agreement_rate"] >= 0.5
        and gradient_report["macro_spearman_p_value"] < 0.05
        and gradient_report["macro_pairwise_concordance_p_value"] < 0.05
    )
    blockers = []
    if plan["task_count"] < PRODUCTION_MINIMUM_TASK_COUNT:
        blockers.append("insufficient_task_population")
    if len(plan["intervention_seeds"]) < PRODUCTION_MINIMUM_INTERVENTION_SEEDS:
        blockers.append("insufficient_numeric_replays")
    if not cross_evaluation_passed:
        blockers.append("cross_evaluation_gradient_rank_gate")
    if not estimation_evidence["passes_rank_gate"]:
        blockers.append("estimation_vs_distribution_intervention_rank_gate")
    if not validation_evidence["passes_rank_gate"]:
        blockers.append("validation_vs_distribution_intervention_rank_gate")
    if max(replay_ranges) > NUMERIC_REPLAY_TOLERANCE:
        blockers.append("numeric_replay_stability")
    eligible_for_core_promotion = not blockers
    report: dict[str, Any] = {
        "experiment_version": DISTRIBUTION_INTERVENTION_VERSION,
        "plan_hash": plan["plan_hash"],
        "intervention_estimand_id": plan["intervention_estimand_id"],
        "source_gradient_report_hash": gradient_report["report_hash"],
        "gradient_estimand_id": gradient_report["gradient_estimand_id"],
        "task_count": plan["task_count"],
        "state_count": plan["state_count"],
        "observation_count": len(rows),
        "intervention_seed_count": len(plan["intervention_seeds"]),
        "epsilon": plan["epsilon"],
        "step_count": plan["step_count"],
        "learning_rate": plan["learning_rate"],
        "task_marginal_policy": plan["task_marginal_policy"],
        "task_marginals": plan["task_marginals"],
        "distribution_formula": plan["distribution_formula"],
        "compute_budget_policy": plan["compute_budget_policy"],
        "numeric_replay_role": plan["intervention_seed_role"],
        "numeric_replay_tolerance": NUMERIC_REPLAY_TOLERANCE,
        "maximum_numeric_replay_range": max(replay_ranges),
        "numeric_replay_stable": max(replay_ranges) <= NUMERIC_REPLAY_TOLERANCE,
        "cross_evaluation_gradient_rank_gate_passed": cross_evaluation_passed,
        "estimation_vs_intervention": estimation_evidence,
        "validation_vs_intervention": validation_evidence,
        "raw_estimation_vs_intervention_diagnostic": raw_estimation_evidence,
        "state_rows": state_rows,
        "eligible_for_core_promotion": eligible_for_core_promotion,
        "production_authorized": False,
        "recommended_production_action": (
            "promote_gradient_projection_contract_in_core"
            if eligible_for_core_promotion
            else "disable_contribution_component"
        ),
        "status": "passed" if eligible_for_core_promotion else "partial",
        "blockers": blockers,
        "claim_boundary": plan["claim_boundary"],
    }
    report["report_hash"] = canonical_hash(
        report,
        prefix="finance_distribution_intervention_report:",
    )
    _write_json(output_dir / "report.json", report)
    print(json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True))


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Validate Gradient Projection with a full-distribution intervention"
    )
    subparsers = parser.add_subparsers(dest="command", required=True)
    prepare_parser = subparsers.add_parser("prepare")
    prepare_parser.add_argument("--source-gradient-dir", required=True)
    prepare_parser.add_argument("--output-dir", required=True)
    prepare_parser.add_argument("--run-role", choices=RUN_ROLES, required=True)
    prepare_parser.add_argument("--epsilon", type=float, default=0.1)
    prepare_parser.add_argument("--step-count", type=int, default=1, choices=(1,))
    prepare_parser.add_argument("--learning-rate", type=float, default=0.00005)
    prepare_parser.add_argument(
        "--intervention-seeds",
        type=int,
        nargs="+",
        default=(20260851, 20260852, 20260853, 20260854),
    )
    prepare_parser.set_defaults(handler=prepare)
    run_parser = subparsers.add_parser("run")
    run_parser.add_argument("--output-dir", required=True)
    run_parser.add_argument("--partitions-per-seed", type=int, default=2)
    run_parser.add_argument("--gpu-ids", type=int, nargs="+", default=(0, 3, 4, 5, 6, 7))
    run_parser.set_defaults(handler=run)
    aggregate_parser = subparsers.add_parser("aggregate")
    aggregate_parser.add_argument("--output-dir", required=True)
    aggregate_parser.set_defaults(handler=aggregate)
    return parser


def main() -> None:
    args = _parser().parse_args()
    args.handler(args)


if __name__ == "__main__":
    main()
