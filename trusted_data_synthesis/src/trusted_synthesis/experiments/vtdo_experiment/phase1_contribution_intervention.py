from __future__ import annotations

import argparse
import gc
import hashlib
import json
import multiprocessing
import os
import random
import statistics
from collections import defaultdict
from concurrent.futures import ProcessPoolExecutor, as_completed
from itertools import combinations
from pathlib import Path
from typing import Any

from trusted_synthesis.experiments.vtdo_experiment.contribution_validation import (
    _cluster_bootstrap_interval,
    _spearman,
)
from trusted_synthesis.experiments.vtdo_experiment.phase1_contribution_population import (
    CONTRIBUTION_POPULATION_VERSION,
    PRODUCTION_CONTRIBUTION_FIELD,
)
from trusted_synthesis.experiments.vtdo_experiment.phase1_probe_gpu import (
    _adapter_tensor_sha256,
    _baseline_lora_model,
    _evaluate,
    _load_records,
    _load_tokenizer,
    _probe_sgd_steps,
    _read_json,
    _seed_everything,
    _train_steps,
    _write_json,
)
from trusted_synthesis.hashing import canonical_hash

CONTRIBUTION_INTERVENTION_VERSION = "finance_contribution_intervention.v4"
INTERVENTION_OPTIMIZERS = ("cold_start_sgd", "cold_start_adamw")


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as source:
        for chunk in iter(lambda: source.read(4 * 1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _append_jsonl(path: Path, value: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as sink:
        sink.write(json.dumps(value, ensure_ascii=False, sort_keys=True) + "\n")
        sink.flush()
        os.fsync(sink.fileno())


def _load_jsonl(path: Path) -> list[dict[str, Any]]:
    if not path.is_file():
        return []
    return [
        json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()
    ]


def prepare(args: argparse.Namespace) -> None:
    if not 1 <= args.intervention_step_count <= 256:
        raise ValueError("intervention_step_count must be between 1 and 256")
    source_dir = Path(args.source_population_dir).resolve()
    output_dir = Path(args.output_dir).resolve()
    output_dir.mkdir(parents=True, exist_ok=True)
    population_plan = _read_json(source_dir / "plan.json")
    population_report = _read_json(source_dir / "report.json")
    if population_report.get("experiment_version") != CONTRIBUTION_POPULATION_VERSION:
        raise ValueError("Intervention requires a current uncertainty-aware population report")
    if population_report.get("production_contribution_field") != PRODUCTION_CONTRIBUTION_FIELD:
        raise ValueError("population report does not freeze the production Contribution signal")
    source_probe_plan = _read_json(Path(population_plan["source_probe_plan_path"]).resolve())
    source_records_path = Path(population_plan["source_records_path"]).resolve()
    target_records_path = Path(population_plan["target_records_path"]).resolve()
    final_test_record_ids = tuple(
        population_plan.get(
            "final_test_record_ids",
            source_probe_plan["final_test_record_ids"],
        )
    )
    if args.intervention_optimizer not in INTERVENTION_OPTIMIZERS:
        raise ValueError("unknown Intervention optimizer contract")
    optimizer_contract = {
        "optimizer": args.intervention_optimizer,
        "learning_rate": args.learning_rate,
        "step_count": args.intervention_step_count,
        "momentum": 0.0,
        "weight_decay": 0.0,
        "gradient_clipping": args.intervention_optimizer == "cold_start_adamw",
        "gradient_clip_norm": (1.0 if args.intervention_optimizer == "cold_start_adamw" else None),
        "optimizer_state_policy": "empty_at_each_task_state",
    }
    optimizer_alignment_role = (
        "same_optimizer_estimand"
        if args.intervention_optimizer == "cold_start_sgd"
        else "optimizer_transfer_diagnostic"
    )
    values: dict[str, Any] = {
        "experiment_version": CONTRIBUTION_INTERVENTION_VERSION,
        "source_population_plan_path": str(source_dir / "plan.json"),
        "source_population_plan_hash": population_plan["plan_hash"],
        "source_population_report_path": str(source_dir / "report.json"),
        "source_population_report_hash": population_report["report_hash"],
        "probe_contribution_signal_kind": PRODUCTION_CONTRIBUTION_FIELD,
        "probe_uncertainty_penalty_coefficient": population_report[
            "uncertainty_penalty_coefficient"
        ],
        "model_dir": population_plan["model_dir"],
        "base_model_manifest_hash": population_plan["base_model_manifest_hash"],
        "beneficiary_adapter_dir": population_plan["beneficiary_adapter_dir"],
        "beneficiary_adapter_tensor_sha256": population_plan["beneficiary_adapter_tensor_sha256"],
        "beneficiary_model_state_id": population_plan["beneficiary_model_state_id"],
        "beneficiary_checkpoint_hash": population_plan["beneficiary_checkpoint_hash"],
        "source_records_path": str(source_records_path),
        "source_records_sha256": _sha256(source_records_path),
        "target_records_path": str(target_records_path),
        "target_records_sha256": _sha256(target_records_path),
        "final_test_record_ids": final_test_record_ids,
        "final_test_set_id": canonical_hash(
            final_test_record_ids,
            prefix="finance_contribution_intervention_final_test:",
        ),
        "jobs": population_plan["jobs"],
        "task_count": population_plan["task_count"],
        "intervention_seeds": tuple(args.intervention_seeds),
        "intervention_step_count": args.intervention_step_count,
        "learning_rate": args.learning_rate,
        "intervention_optimizer": args.intervention_optimizer,
        "optimizer_contract": optimizer_contract,
        "optimizer_alignment_role": optimizer_alignment_role,
        "metric": "negative_supervised_token_nll",
        "evaluation_role": "untouched_final_test",
        "claim_boundary": (
            "This is an independent-seed finite local Intervention at a frozen adaptation "
            "horizon on an untouched final-test set. Same-optimizer SGD runs test local "
            "Probe validity; AdamW runs only test optimizer transfer. Neither is a full "
            "Student training experiment."
        ),
    }
    values["intervention_estimand_id"] = canonical_hash(
        {
            "beneficiary_checkpoint_hash": values["beneficiary_checkpoint_hash"],
            "final_test_set_id": values["final_test_set_id"],
            "target_records_sha256": values["target_records_sha256"],
            "metric": values["metric"],
            "evaluation_role": values["evaluation_role"],
            "intervention_step_count": values["intervention_step_count"],
            "learning_rate": values["learning_rate"],
            "optimizer_contract": values["optimizer_contract"],
            "optimizer_alignment_role": values["optimizer_alignment_role"],
        },
        prefix="finance_contribution_intervention_estimand:",
    )
    values["plan_hash"] = canonical_hash(
        values,
        prefix="finance_contribution_intervention_plan:",
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
    from peft import get_peft_model_state_dict, set_peft_model_state_dict

    plan = _read_json(Path(plan_path))
    if plan.get("experiment_version") != CONTRIBUTION_INTERVENTION_VERSION:
        raise ValueError("Intervention worker requires a freshly prepared v4 plan")
    if plan.get("intervention_optimizer") not in INTERVENTION_OPTIMIZERS:
        raise ValueError("Intervention worker received an unknown optimizer contract")
    if _sha256(Path(plan["source_records_path"])) != plan["source_records_sha256"]:
        raise ValueError("source records changed after Intervention planning")
    if _sha256(Path(plan["target_records_path"])) != plan["target_records_sha256"]:
        raise ValueError("target records changed after Intervention planning")
    output_dir = Path(plan_path).parent
    worker_path = output_dir / "workers" / f"seed_{seed}_partition_{partition_index}.jsonl"
    completed = {
        item["job_id"] for item in _load_jsonl(worker_path) if item.get("status") == "passed"
    }
    jobs = [
        job for index, job in enumerate(plan["jobs"]) if index % partition_count == partition_index
    ]
    records = _load_records(Path(plan["target_records_path"]))
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
        raise ValueError("Intervention worker loaded another beneficiary Adapter")
    baseline_performance, baseline_loss, final_test_tokens = _evaluate(
        model,
        tokenizer,
        final_records,
    )
    baseline_state = {
        name: tensor.detach().cpu().clone()
        for name, tensor in get_peft_model_state_dict(model).items()
    }
    completed_now = 0
    for job in jobs:
        if job["job_id"] in completed:
            continue
        _seed_everything(seed)
        load_result = set_peft_model_state_dict(
            model,
            baseline_state,
            adapter_name="default",
        )
        if getattr(load_result, "unexpected_keys", ()):
            raise ValueError("beneficiary restore produced unexpected Adapter keys")
        update_steps = (
            _probe_sgd_steps if plan["intervention_optimizer"] == "cold_start_sgd" else _train_steps
        )
        losses = update_steps(
            model,
            tokenizer,
            (records[job["record_id"]],),
            step_count=int(plan["intervention_step_count"]),
            learning_rate=float(plan["learning_rate"]),
        )
        adapted_performance, adapted_loss, adapted_tokens = _evaluate(
            model,
            tokenizer,
            final_records,
        )
        if adapted_tokens != final_test_tokens:
            raise ValueError("Intervention changed final-test token support")
        result = {
            **job,
            "experiment_version": CONTRIBUTION_INTERVENTION_VERSION,
            "plan_hash": plan["plan_hash"],
            "gpu_id": gpu_id,
            "gpu_name": torch.cuda.get_device_name(0),
            "seed": seed,
            "partition_index": partition_index,
            "intervention_optimizer": plan["intervention_optimizer"],
            "optimizer_alignment_role": plan["optimizer_alignment_role"],
            "status": "passed",
            "baseline_performance": baseline_performance,
            "baseline_loss": baseline_loss,
            "adapted_performance": adapted_performance,
            "adapted_loss": adapted_loss,
            "performance_gain": adapted_performance - baseline_performance,
            "training_losses": losses,
            "final_test_supervised_tokens": final_test_tokens,
            "adapted_adapter_tensor_sha256": _adapter_tensor_sha256(model),
        }
        result["result_hash"] = canonical_hash(
            result,
            prefix="finance_contribution_intervention_result:",
        )
        _append_jsonl(worker_path, result)
        completed_now += 1
    report = {
        "seed": seed,
        "gpu_id": gpu_id,
        "partition_index": partition_index,
        "partition_count": partition_count,
        "job_count": len(jobs),
        "completed_before_resume": len(completed),
        "completed_now": completed_now,
        "baseline_performance": baseline_performance,
        "peak_gpu_memory_bytes": int(torch.cuda.max_memory_allocated()),
    }
    del model
    gc.collect()
    torch.cuda.empty_cache()
    return report


def run(args: argparse.Namespace) -> None:
    output_dir = Path(args.output_dir).resolve()
    plan_path = output_dir / "plan.json"
    plan = _read_json(plan_path)
    seeds = tuple(int(item) for item in plan["intervention_seeds"])
    worker_specs = [
        (seed, partition) for seed in seeds for partition in range(args.partitions_per_seed)
    ]
    if len(args.gpu_ids) < len(worker_specs):
        raise ValueError("one isolated GPU is required per Intervention worker")
    context = multiprocessing.get_context("spawn")
    reports = []
    with ProcessPoolExecutor(
        max_workers=len(worker_specs),
        mp_context=context,
    ) as executor:
        futures = {
            executor.submit(
                _worker,
                str(plan_path),
                gpu_id=gpu_id,
                seed=seed,
                partition_index=partition,
                partition_count=args.partitions_per_seed,
            ): (gpu_id, seed, partition)
            for gpu_id, (seed, partition) in zip(
                args.gpu_ids,
                worker_specs,
                strict=True,
            )
        }
        for future in as_completed(futures):
            reports.append(future.result())
    _write_json(
        output_dir / "worker_summary.json",
        {
            "workers": sorted(
                reports,
                key=lambda item: (item["seed"], item["partition_index"]),
            )
        },
    )
    print(json.dumps(reports, ensure_ascii=False, indent=2, sort_keys=True))


def _pairwise_concordance(left: list[float], right: list[float]) -> float:
    matches = 0
    count = 0
    for first, second in combinations(range(len(left)), 2):
        left_delta = left[first] - left[second]
        right_delta = right[first] - right[second]
        if left_delta == 0 and right_delta == 0:
            continue
        matches += int((left_delta > 0) == (right_delta > 0))
        count += 1
    return matches / count if count else 0.0


def _quantile(values: list[float], probability: float) -> float:
    ordered = sorted(values)
    index = round((len(ordered) - 1) * probability)
    return ordered[index]


def _permutation_null(
    task_vectors: list[tuple[list[float], list[float]]],
    *,
    iterations: int,
    seed: int,
) -> tuple[list[float], list[float]]:
    rng = random.Random(seed)
    spearman_values = []
    concordance_values = []
    for _ in range(iterations):
        task_spearman = []
        task_concordance = []
        for probe, intervention in task_vectors:
            shuffled = list(probe)
            rng.shuffle(shuffled)
            task_spearman.append(_spearman(shuffled, intervention))
            task_concordance.append(_pairwise_concordance(shuffled, intervention))
        spearman_values.append(statistics.fmean(task_spearman))
        concordance_values.append(statistics.fmean(task_concordance))
    return spearman_values, concordance_values


def _task_rank_row(
    task_id: str,
    task_states: list[dict[str, Any]],
) -> tuple[dict[str, Any], tuple[list[float], list[float]]]:
    production = [
        float(item["probe_estimation_conservative_centered_contribution"]) for item in task_states
    ]
    raw = [float(item["probe_estimation_centered_contribution"]) for item in task_states]
    intervention = [float(item["intervention_mean_gain"]) for item in task_states]
    return (
        {
            "task_id": task_id,
            "task_type": task_states[0]["task_type"],
            "spearman": _spearman(production, intervention),
            "pairwise_concordance": _pairwise_concordance(production, intervention),
            "raw_centered_spearman": _spearman(raw, intervention),
            "raw_centered_pairwise_concordance": _pairwise_concordance(raw, intervention),
        },
        (production, intervention),
    )


def aggregate(args: argparse.Namespace) -> None:
    output_dir = Path(args.output_dir).resolve()
    plan = _read_json(output_dir / "plan.json")
    population = _read_json(Path(plan["source_population_report_path"]))
    if plan.get("experiment_version") != CONTRIBUTION_INTERVENTION_VERSION:
        raise ValueError("Intervention aggregate requires a freshly prepared v4 plan")
    if population.get("report_hash") != plan["source_population_report_hash"]:
        raise ValueError("source population report changed after Intervention planning")
    if plan.get("probe_contribution_signal_kind") != PRODUCTION_CONTRIBUTION_FIELD:
        raise ValueError("Intervention plan does not target the production Contribution signal")
    rows = [
        item
        for path in sorted((output_dir / "workers").glob("*.jsonl"))
        for item in _load_jsonl(path)
    ]
    expected = len(plan["jobs"]) * len(plan["intervention_seeds"])
    if len(rows) != expected:
        raise ValueError(f"Intervention matrix is incomplete: {len(rows)} != {expected}")
    if {item["plan_hash"] for item in rows} != {plan["plan_hash"]}:
        raise ValueError("Intervention rows cross frozen plan identities")
    if {item["experiment_version"] for item in rows} != {plan["experiment_version"]}:
        raise ValueError("Intervention rows cross experiment versions")
    if {item["intervention_optimizer"] for item in rows} != {plan["intervention_optimizer"]}:
        raise ValueError("Intervention rows cross optimizer contracts")
    if {item["optimizer_alignment_role"] for item in rows} != {plan["optimizer_alignment_role"]}:
        raise ValueError("Intervention rows cross optimizer alignment roles")
    by_key = {(item["task_id"], item["state_id"], item["seed"]): item for item in rows}
    if len(by_key) != len(rows):
        raise ValueError("Intervention matrix contains duplicate task/state/seed rows")
    baseline_values = {round(float(item["baseline_performance"]), 12) for item in rows}
    if len(baseline_values) != 1:
        raise ValueError("Intervention workers disagree on frozen baseline performance")
    estimated = {(item["task_id"], item["state_id"]): item for item in population["state_rows"]}
    intervention_values: defaultdict[tuple[str, str], list[float]] = defaultdict(list)
    representatives: dict[tuple[str, str], dict[str, Any]] = {}
    for row in rows:
        key = (row["task_id"], row["state_id"])
        intervention_values[key].append(row["performance_gain"])
        representatives[key] = row
    state_rows = []
    for key, gains in sorted(intervention_values.items()):
        source = estimated[key]
        representative = representatives[key]
        state_rows.append(
            {
                "task_id": key[0],
                "task_type": representative["task_type"],
                "state_id": key[1],
                "strategy": representative["strategy"],
                "probe_estimation_mean_gain": source["estimation_mean_gain"],
                "probe_estimation_centered_contribution": source[
                    "estimation_centered_contribution"
                ],
                "probe_estimation_conservative_centered_contribution": source[
                    PRODUCTION_CONTRIBUTION_FIELD
                ],
                "intervention_mean_gain": statistics.fmean(gains),
                "intervention_seed_gains": gains,
            }
        )
    grouped: defaultdict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in state_rows:
        grouped[row["task_id"]].append(row)
    task_rows = []
    task_vectors = []
    for task_id, task_states in sorted(grouped.items()):
        task_states.sort(key=lambda item: item["state_id"])
        task_row, task_vector = _task_rank_row(task_id, task_states)
        task_rows.append(task_row)
        task_vectors.append(task_vector)
    spearman = [item["spearman"] for item in task_rows]
    concordance = [item["pairwise_concordance"] for item in task_rows]
    raw_spearman = [item["raw_centered_spearman"] for item in task_rows]
    raw_concordance = [item["raw_centered_pairwise_concordance"] for item in task_rows]
    observed_spearman = statistics.fmean(spearman)
    observed_concordance = statistics.fmean(concordance)
    null_spearman, null_concordance = _permutation_null(
        task_vectors,
        iterations=10000,
        seed=20260833,
    )
    strategy_intervention: defaultdict[str, list[float]] = defaultdict(list)
    for row in state_rows:
        strategy_intervention[row["strategy"]].append(row["intervention_mean_gain"])
    report: dict[str, Any] = {
        "experiment_version": plan["experiment_version"],
        "plan_hash": plan["plan_hash"],
        "intervention_estimand_id": plan.get("intervention_estimand_id"),
        "intervention_step_count": plan["intervention_step_count"],
        "learning_rate": plan["learning_rate"],
        "intervention_optimizer": plan["intervention_optimizer"],
        "optimizer_contract": plan["optimizer_contract"],
        "optimizer_alignment_role": plan["optimizer_alignment_role"],
        "evaluation_role": plan.get("evaluation_role", "untouched_final_test"),
        "final_test_set_id": plan["final_test_set_id"],
        "source_population_report_hash": population["report_hash"],
        "probe_contribution_signal_kind": plan["probe_contribution_signal_kind"],
        "probe_uncertainty_penalty_coefficient": plan["probe_uncertainty_penalty_coefficient"],
        "task_count": len(task_rows),
        "state_count": len(state_rows),
        "observation_count": len(rows),
        "intervention_seed_count": len(plan["intervention_seeds"]),
        "baseline_final_test_performance": next(iter(baseline_values)),
        "macro_task_spearman": observed_spearman,
        "macro_task_spearman_ci95": _cluster_bootstrap_interval(
            spearman,
            samples=2000,
            seed=20260831,
        ),
        "macro_pairwise_concordance": observed_concordance,
        "macro_pairwise_concordance_ci95": _cluster_bootstrap_interval(
            concordance,
            samples=2000,
            seed=20260832,
        ),
        "raw_centered_macro_task_spearman": statistics.fmean(raw_spearman),
        "raw_centered_macro_pairwise_concordance": statistics.fmean(raw_concordance),
        "conservative_minus_raw_spearman": observed_spearman - statistics.fmean(raw_spearman),
        "conservative_minus_raw_pairwise_concordance": observed_concordance
        - statistics.fmean(raw_concordance),
        "permutation_test": {
            "iterations": 10000,
            "seed": 20260833,
            "null_macro_spearman_mean": statistics.fmean(null_spearman),
            "null_macro_spearman_interval95": [
                _quantile(null_spearman, 0.025),
                _quantile(null_spearman, 0.975),
            ],
            "macro_spearman_p_value": (
                1 + sum(value >= observed_spearman for value in null_spearman)
            )
            / (len(null_spearman) + 1),
            "null_macro_pairwise_concordance_mean": statistics.fmean(null_concordance),
            "null_macro_pairwise_concordance_interval95": [
                _quantile(null_concordance, 0.025),
                _quantile(null_concordance, 0.975),
            ],
            "macro_pairwise_concordance_p_value": (
                1 + sum(value >= observed_concordance for value in null_concordance)
            )
            / (len(null_concordance) + 1),
        },
        "strategy_intervention_mean_gain": {
            strategy: statistics.fmean(values)
            for strategy, values in sorted(strategy_intervention.items())
        },
        "task_rows": task_rows,
        "state_rows": state_rows,
        "status": "partial",
        "claim_boundary": plan["claim_boundary"],
        "target_population_validation_task_count": 30,
        "population_validation_gap": max(30 - len(task_rows), 0),
    }
    report["report_hash"] = canonical_hash(
        report,
        prefix="finance_contribution_intervention_report:",
    )
    _write_json(output_dir / "report.json", report)
    print(json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True))


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Run independent finite local Interventions for Contribution validation"
    )
    subparsers = parser.add_subparsers(dest="command", required=True)
    prepare_parser = subparsers.add_parser("prepare")
    prepare_parser.add_argument("--source-population-dir", required=True)
    prepare_parser.add_argument("--output-dir", required=True)
    prepare_parser.add_argument("--intervention-step-count", type=int, default=12)
    prepare_parser.add_argument("--learning-rate", type=float, default=0.0002)
    prepare_parser.add_argument(
        "--intervention-optimizer",
        required=True,
        choices=INTERVENTION_OPTIMIZERS,
    )
    prepare_parser.add_argument(
        "--intervention-seeds",
        type=int,
        nargs="+",
        default=(20260831, 20260832),
    )
    prepare_parser.set_defaults(handler=prepare)

    run_parser = subparsers.add_parser("run")
    run_parser.add_argument("--output-dir", required=True)
    run_parser.add_argument("--partitions-per-seed", type=int, default=2)
    run_parser.add_argument("--gpu-ids", type=int, nargs="+", default=(3, 4, 5, 6))
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
