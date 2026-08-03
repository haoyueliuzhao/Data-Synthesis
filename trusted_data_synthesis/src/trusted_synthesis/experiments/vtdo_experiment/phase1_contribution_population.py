from __future__ import annotations

import argparse
import gc
import hashlib
import json
import math
import multiprocessing
import os
import statistics
from collections import defaultdict
from concurrent.futures import ProcessPoolExecutor, as_completed
from itertools import combinations
from pathlib import Path
from typing import Any

from trusted_synthesis.core.vtdo import (
    contribution_current_distribution_hash,
    contribution_distribution_contract_hash,
)
from trusted_synthesis.experiments.vtdo_experiment.contribution_validation import (
    _cluster_bootstrap_interval,
    _spearman,
)
from trusted_synthesis.experiments.vtdo_experiment.multistate import (
    FinanceTaskStateArtifact,
    load_finance_multi_state_artifacts,
)
from trusted_synthesis.experiments.vtdo_experiment.phase1_probe_gpu import (
    MAX_SEQUENCE_LENGTH,
    TARGET_STRATEGIES,
    _adapter_tensor_sha256,
    _baseline_lora_model,
    _encode_record,
    _evaluate,
    _load_records,
    _load_tokenizer,
    _probe_sgd_steps,
    _read_json,
    _record_from_state,
    _seed_everything,
    _selected_states,
    _write_json,
)
from trusted_synthesis.experiments.vtdo_experiment.schema import VTDOTrainingRecord
from trusted_synthesis.hashing import canonical_hash

CONTRIBUTION_POPULATION_VERSION = "finance_contribution_population_probe.v5"
PRODUCTION_CONTRIBUTION_FIELD = "estimation_conservative_centered_contribution"
PENALTY_SENSITIVITY_GRID = (0.0, 0.25, 0.5, 1.0, 2.0)
PRODUCTION_MINIMUM_SEEDS_PER_SPLIT = 4
PROBE_RUN_ROLES = ("production_candidate", "horizon_validation_only")
CENTERING_POLICY = "uniform_state_weighted_after_uncertainty_penalty"
STATE_PROBABILITY_POLICY = "uniform_over_selected_states"


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


def _select_tasks(
    artifacts: tuple[FinanceTaskStateArtifact, ...],
    *,
    count: int,
    excluded_task_ids: set[str],
) -> tuple[FinanceTaskStateArtifact, ...]:
    groups: defaultdict[str, list[FinanceTaskStateArtifact]] = defaultdict(list)
    for artifact in artifacts:
        if artifact.omega.task.task_id in excluded_task_ids:
            continue
        if not all(
            strategy in {item.strategy for item in artifact.accepted_states}
            for strategy in TARGET_STRATEGIES
        ):
            continue
        groups[artifact.omega.task.public.task_type].append(artifact)
    for values in groups.values():
        values.sort(
            key=lambda item: (
                sum(len(state.trajectory.model_dump_json()) for state in _selected_states(item)),
                item.artifact_id,
            )
        )
    selected: list[FinanceTaskStateArtifact] = []
    cursor = 0
    group_names = tuple(sorted(groups))
    while len(selected) < count:
        progressed = False
        for name in group_names:
            values = groups[name]
            if cursor >= len(values):
                continue
            selected.append(values[cursor])
            progressed = True
            if len(selected) == count:
                break
        if not progressed:
            break
        cursor += 1
    if len(selected) < count:
        raise ValueError(f"only {len(selected)} eligible target tasks for requested {count}")
    return tuple(selected)


def _validate_probe_replication_contract(
    *,
    probe_step_count: int,
    probe_seeds: tuple[int, ...],
    run_role: str,
) -> None:
    if run_role not in PROBE_RUN_ROLES:
        raise ValueError("unknown Probe run role")
    if probe_step_count not in (1, 3, 5):
        raise ValueError("Probe validation horizons are restricted to 1, 3, or 5")
    if len(probe_seeds) < 4 or len(probe_seeds) % 2:
        raise ValueError("Contribution population requires an even number of at least four seeds")
    if len(set(probe_seeds)) != len(probe_seeds):
        raise ValueError("Contribution population seeds must be unique")
    seeds_per_split = len(probe_seeds) // 2
    if run_role == "production_candidate":
        if probe_step_count > 3:
            raise ValueError("production Probe candidates support only one or three SGD steps")
        if seeds_per_split < PRODUCTION_MINIMUM_SEEDS_PER_SPLIT:
            raise ValueError("production Probe candidates require at least four seeds per split")


def _seed_waves(
    seeds: tuple[int, ...],
    gpu_ids: tuple[int, ...],
) -> tuple[tuple[tuple[int, int], ...], ...]:
    if not gpu_ids or len(set(gpu_ids)) != len(gpu_ids):
        raise ValueError("Probe run requires at least one unique GPU id")
    waves = []
    for start in range(0, len(seeds), len(gpu_ids)):
        seed_wave = seeds[start : start + len(gpu_ids)]
        waves.append(tuple(zip(gpu_ids, seed_wave, strict=False)))
    return tuple(waves)


def prepare(args: argparse.Namespace) -> None:
    if args.uncertainty_penalty_coefficient <= 0:
        raise ValueError("uncertainty_penalty_coefficient must be positive")
    _validate_probe_replication_contract(
        probe_step_count=args.probe_step_count,
        probe_seeds=tuple(args.probe_seeds),
        run_role=args.run_role,
    )
    output_dir = Path(args.output_dir).resolve()
    output_dir.mkdir(parents=True, exist_ok=True)
    source_plan = _read_json(Path(args.source_probe_plan).resolve())
    source_baseline = _read_json(Path(args.source_baseline_report).resolve())
    excluded = set(source_plan["baseline_record_ids"])
    source_records_path = Path(source_plan["records_path"]).resolve()
    source_records = _load_records(source_records_path)
    excluded_task_ids = {
        source_records[record_id].task_id
        for record_id in (
            set(source_plan["baseline_record_ids"])
            | set(source_plan["internal_validation_record_ids"])
            | set(source_plan["final_test_record_ids"])
        )
    }
    additional_excluded_task_ids = source_plan.get("additional_excluded_task_ids", ())
    if not isinstance(additional_excluded_task_ids, (list, tuple)) or any(
        not isinstance(task_id, str) or not task_id for task_id in additional_excluded_task_ids
    ):
        raise ValueError("additional excluded task identities are invalid")
    excluded_task_ids.update(additional_excluded_task_ids)
    del excluded
    artifacts = load_finance_multi_state_artifacts(Path(args.artifacts_path).resolve())
    selected = _select_tasks(
        artifacts,
        count=args.task_count,
        excluded_task_ids=excluded_task_ids,
    )
    target_records: list[VTDOTrainingRecord] = []
    jobs: list[dict[str, Any]] = []
    for artifact in selected:
        for state in _selected_states(artifact):
            record = _record_from_state(
                artifact,
                state,
                "B2_validity",
                sampling_weight=1.0,
            )
            target_records.append(record)
            jobs.append(
                {
                    "job_id": canonical_hash(
                        {
                            "task_id": artifact.omega.task.task_id,
                            "state_id": state.assignment.state.state_id,
                            "record_id": record.record_id,
                        },
                        prefix="contribution_population_job:",
                    ),
                    "task_id": artifact.omega.task.task_id,
                    "task_type": artifact.omega.task.public.task_type,
                    "state_id": state.assignment.state.state_id,
                    "strategy": state.strategy,
                    "record_id": record.record_id,
                }
            )
    record_path = output_dir / "target_records.jsonl"
    record_path.write_text(
        "".join(item.model_dump_json() + "\n" for item in target_records),
        encoding="utf-8",
    )
    validation_ids = tuple(source_plan["internal_validation_record_ids"])
    final_test_ids = tuple(source_plan["final_test_record_ids"])
    split_index = len(args.probe_seeds) // 2
    model_dir = Path(source_plan["model_dir"]).resolve()
    tokenizer = _load_tokenizer(model_dir)
    token_audit = {}
    for record in target_records:
        encoded = _encode_record(tokenizer, record, MAX_SEQUENCE_LENGTH)
        token_audit[record.record_id] = {
            "processed_tokens": len(encoded["input_ids"]),
            "prompt_tokens": int(encoded["prompt_tokens"]),
            "supervised_tokens": int(encoded["supervised_tokens"]),
        }
    values = {
        "experiment_version": CONTRIBUTION_POPULATION_VERSION,
        "artifacts_path": str(Path(args.artifacts_path).resolve()),
        "source_probe_plan_path": str(Path(args.source_probe_plan).resolve()),
        "source_probe_plan_hash": source_plan["plan_hash"],
        "source_baseline_report_path": str(Path(args.source_baseline_report).resolve()),
        "source_baseline_report_hash": source_baseline["report_hash"],
        "model_dir": str(model_dir),
        "base_model_manifest_hash": source_plan["base_model_manifest_hash"],
        "beneficiary_adapter_dir": source_baseline["adapter_dir"],
        "beneficiary_adapter_tensor_sha256": source_baseline["adapter_tensor_sha256"],
        "beneficiary_model_state_id": source_baseline["model_state_id"],
        "beneficiary_checkpoint_hash": source_baseline["checkpoint_hash"],
        "baseline_performance": source_baseline["validation_performance"],
        "source_records_path": str(source_records_path),
        "source_records_sha256": _sha256(source_records_path),
        "validation_record_ids": validation_ids,
        "final_test_record_ids": final_test_ids,
        "internal_validation_set_id": canonical_hash(
            validation_ids,
            prefix="finance_contribution_internal_validation:",
        ),
        "final_test_set_id": canonical_hash(
            final_test_ids,
            prefix="finance_contribution_final_test:",
        ),
        "excluded_task_ids": tuple(sorted(excluded_task_ids)),
        "selected_task_ids": tuple(artifact.omega.task.task_id for artifact in selected),
        "task_count": len(selected),
        "jobs": jobs,
        "target_records_path": str(record_path),
        "target_records_sha256": _sha256(record_path),
        "probe_seeds": tuple(args.probe_seeds),
        "estimation_seeds": tuple(args.probe_seeds[:split_index]),
        "validation_seeds": tuple(args.probe_seeds[split_index:]),
        "probe_step_count": args.probe_step_count,
        "learning_rate": args.learning_rate,
        "probe_optimizer": "cold_start_sgd",
        "probe_usage_scope": args.run_role,
        "seed_replicates_per_split": split_index,
        "minimum_production_seed_replicates_per_split": (PRODUCTION_MINIMUM_SEEDS_PER_SPLIT),
        "uncertainty_statistic": "sample_standard_deviation",
        "uncertainty_penalty_coefficient": args.uncertainty_penalty_coefficient,
        "centering_policy": CENTERING_POLICY,
        "state_probability_policy": STATE_PROBABILITY_POLICY,
        "maximum_sequence_length": MAX_SEQUENCE_LENGTH,
        "token_audit": token_audit,
        "semantic_limitation": (
            "This experiment measures seed-disjoint local-Probe rank stability. It is not "
            "the independent finite-Intervention Contribution validation."
        ),
    }
    values["probe_estimand_id"] = canonical_hash(
        {
            "beneficiary_checkpoint_hash": values["beneficiary_checkpoint_hash"],
            "internal_validation_set_id": values["internal_validation_set_id"],
            "source_records_sha256": values["source_records_sha256"],
            "metric": "negative_supervised_token_nll",
            "evaluation_role": "internal_validation",
            "probe_step_count": values["probe_step_count"],
            "learning_rate": values["learning_rate"],
            "optimizer": "cold_start_sgd",
            "uncertainty_statistic": values["uncertainty_statistic"],
            "uncertainty_penalty_coefficient": values["uncertainty_penalty_coefficient"],
            "centering_policy": values["centering_policy"],
        },
        prefix="finance_contribution_probe_estimand:",
    )
    values["plan_hash"] = canonical_hash(
        values,
        prefix="finance_contribution_population_plan:",
    )
    _write_json(output_dir / "plan.json", values)
    print(json.dumps(values, ensure_ascii=False, indent=2, sort_keys=True))


def _worker(
    plan_path: str,
    *,
    gpu_id: int,
    seed: int,
) -> dict[str, Any]:
    os.environ["CUDA_VISIBLE_DEVICES"] = str(gpu_id)
    import torch
    from peft import get_peft_model_state_dict, set_peft_model_state_dict

    plan = _read_json(Path(plan_path))
    if (
        plan.get("experiment_version") != CONTRIBUTION_POPULATION_VERSION
        or plan.get("probe_optimizer") != "cold_start_sgd"
        or plan.get("uncertainty_statistic") != "sample_standard_deviation"
        or plan.get("centering_policy") != CENTERING_POLICY
        or plan.get("state_probability_policy") != STATE_PROBABILITY_POLICY
    ):
        raise ValueError("population worker requires the v5 first-order Probe contract")
    if _sha256(Path(plan["source_records_path"])) != plan["source_records_sha256"]:
        raise ValueError("source records changed after Contribution planning")
    if _sha256(Path(plan["target_records_path"])) != plan["target_records_sha256"]:
        raise ValueError("target records changed after Contribution planning")
    output_dir = Path(plan_path).parent
    worker_path = output_dir / "workers" / f"seed_{seed}.jsonl"
    completed = {
        item["job_id"] for item in _load_jsonl(worker_path) if item.get("status") == "passed"
    }
    records = _load_records(Path(plan["target_records_path"]))
    source_records = _load_records(Path(plan["source_records_path"]))
    validation_records = tuple(
        source_records[record_id] for record_id in plan["validation_record_ids"]
    )
    _seed_everything(seed)
    torch.cuda.reset_peak_memory_stats()
    tokenizer = _load_tokenizer(Path(plan["model_dir"]))
    model = _baseline_lora_model(
        Path(plan["model_dir"]),
        Path(plan["beneficiary_adapter_dir"]),
    )
    loaded_hash = _adapter_tensor_sha256(model)
    if loaded_hash != plan["beneficiary_adapter_tensor_sha256"]:
        raise ValueError("population worker loaded another beneficiary Adapter")
    loaded_performance, _, _ = _evaluate(
        model,
        tokenizer,
        validation_records,
    )
    expected_baseline_performance = float(plan["baseline_performance"])
    replay_tolerance = 5e-7
    if not math.isclose(
        loaded_performance,
        expected_baseline_performance,
        rel_tol=0.0,
        abs_tol=replay_tolerance,
    ):
        raise ValueError(
            "population worker did not replay baseline performance:"
            f"expected={expected_baseline_performance:.12f},"
            f"observed={loaded_performance:.12f},"
            f"delta={loaded_performance - expected_baseline_performance:.12g},"
            f"tolerance={replay_tolerance:.12g}"
        )
    baseline_state = {
        name: tensor.detach().cpu().clone()
        for name, tensor in get_peft_model_state_dict(model).items()
    }
    completed_now = 0
    for job in plan["jobs"]:
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
        losses = _probe_sgd_steps(
            model,
            tokenizer,
            (records[job["record_id"]],),
            step_count=int(plan["probe_step_count"]),
            learning_rate=float(plan["learning_rate"]),
        )
        adapted_performance, adapted_loss, validation_tokens = _evaluate(
            model,
            tokenizer,
            validation_records,
        )
        result = {
            **job,
            "experiment_version": plan["experiment_version"],
            "plan_hash": plan["plan_hash"],
            "gpu_id": gpu_id,
            "gpu_name": torch.cuda.get_device_name(0),
            "seed": seed,
            "status": "passed",
            "baseline_performance": loaded_performance,
            "adapted_performance": adapted_performance,
            "adapted_loss": adapted_loss,
            "performance_gain": adapted_performance - loaded_performance,
            "training_losses": losses,
            "validation_supervised_tokens": validation_tokens,
            "adapted_adapter_tensor_sha256": _adapter_tensor_sha256(model),
        }
        result["result_hash"] = canonical_hash(
            result,
            prefix="finance_contribution_population_result:",
        )
        _append_jsonl(worker_path, result)
        completed_now += 1
    report = {
        "seed": seed,
        "gpu_id": gpu_id,
        "completed_before_resume": len(completed),
        "completed_now": completed_now,
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
    if plan.get("experiment_version") != CONTRIBUTION_POPULATION_VERSION:
        raise ValueError("population run requires a freshly prepared v5 plan")
    seeds = tuple(int(item) for item in plan["probe_seeds"])
    gpu_ids = tuple(args.gpu_ids)
    context = multiprocessing.get_context("spawn")
    reports = []
    for wave_index, wave in enumerate(_seed_waves(seeds, gpu_ids)):
        with ProcessPoolExecutor(
            max_workers=len(wave),
            mp_context=context,
        ) as executor:
            futures = {
                executor.submit(
                    _worker,
                    str(plan_path),
                    gpu_id=gpu_id,
                    seed=seed,
                ): (gpu_id, seed)
                for gpu_id, seed in wave
            }
            for future in as_completed(futures):
                report = future.result()
                report["wave_index"] = wave_index
                reports.append(report)
    _write_json(
        output_dir / "worker_summary.json",
        {"workers": sorted(reports, key=lambda item: item["seed"])},
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


def _sample_standard_deviation(values: list[float]) -> float:
    if len(values) < 2:
        raise ValueError("uncertainty-aware Probe requires at least two seeds")
    return statistics.stdev(values)


def _current_state_probabilities(
    state_rows: list[dict[str, Any]],
    *,
    policy: str,
) -> dict[str, float]:
    """Replay the frozen pi_t used by this population experiment.

    The completed v5 GPU observations intentionally evaluate the uniform initial
    conditional distribution. Core VTDO supports arbitrary pi_t; this experiment
    identifies its uniform special case instead of treating an arithmetic mean as
    the general estimator.
    """

    if policy != STATE_PROBABILITY_POLICY:
        raise ValueError(f"unsupported population state-probability policy:{policy}")
    state_ids = [str(row["state_id"]) for row in state_rows]
    if not state_ids or len(state_ids) != len(set(state_ids)):
        raise ValueError("population task requires unique non-empty states")
    probability = 1.0 / len(state_ids)
    return {state_id: probability for state_id in sorted(state_ids)}


def _current_distribution_hash(
    task_id: str,
    probabilities: dict[str, float],
) -> str:
    return contribution_current_distribution_hash(task_id, probabilities)


def _attach_contribution_signals(
    state_rows: list[dict[str, Any]],
    *,
    split: str,
    penalty_coefficient: float,
    state_probabilities: dict[str, float],
) -> None:
    mean_field = f"{split}_mean_gain"
    seed_field = f"{split}_seed_gains"
    centered_field = f"{split}_centered_contribution"
    deviation_field = f"{split}_sample_standard_deviation"
    penalty_field = f"{split}_uncertainty_penalty"
    conservative_raw_field = f"{split}_conservative_raw_gain"
    conservative_field = f"{split}_conservative_centered_contribution"
    state_ids = {str(row["state_id"]) for row in state_rows}
    if set(state_probabilities) != state_ids:
        raise ValueError("Contribution probabilities do not cover the task states exactly")
    if any(value <= 0 or not math.isfinite(value) for value in state_probabilities.values()):
        raise ValueError("Contribution probabilities must be finite and positive")
    if not math.isclose(sum(state_probabilities.values()), 1.0, abs_tol=1e-12):
        raise ValueError("Contribution probabilities must sum to one")
    mean_baseline = sum(
        state_probabilities[str(row["state_id"])] * float(row[mean_field]) for row in state_rows
    )
    for row in state_rows:
        probability = state_probabilities[str(row["state_id"])]
        deviation = _sample_standard_deviation(list(row[seed_field]))
        penalty = penalty_coefficient * deviation
        row["current_probability"] = probability
        row[deviation_field] = deviation
        row[penalty_field] = penalty
        row[centered_field] = float(row[mean_field]) - mean_baseline
        row[conservative_raw_field] = float(row[mean_field]) - penalty
    conservative_baseline = sum(
        state_probabilities[str(row["state_id"])] * float(row[conservative_raw_field])
        for row in state_rows
    )
    for row in state_rows:
        row[conservative_field] = float(row[conservative_raw_field]) - conservative_baseline
    for field in (centered_field, conservative_field):
        weighted_mean = sum(
            state_probabilities[str(row["state_id"])] * float(row[field]) for row in state_rows
        )
        if not math.isclose(weighted_mean, 0.0, abs_tol=1e-12):
            raise ValueError(f"{field} is not centered under the frozen pi_t")


def _penalty_sensitivity_rows(
    grouped: dict[str, list[dict[str, Any]]],
) -> list[dict[str, float]]:
    rows = []
    for coefficient in PENALTY_SENSITIVITY_GRID:
        task_spearman = []
        task_concordance = []
        for states in grouped.values():
            estimation = [
                float(item["estimation_mean_gain"])
                - coefficient * _sample_standard_deviation(item["estimation_seed_gains"])
                for item in states
            ]
            validation = [
                float(item["validation_mean_gain"])
                - coefficient * _sample_standard_deviation(item["validation_seed_gains"])
                for item in states
            ]
            task_spearman.append(_spearman(estimation, validation))
            task_concordance.append(_pairwise_concordance(estimation, validation))
        rows.append(
            {
                "penalty_coefficient": coefficient,
                "macro_task_spearman": statistics.fmean(task_spearman),
                "macro_pairwise_concordance": statistics.fmean(task_concordance),
            }
        )
    return rows


def aggregate(args: argparse.Namespace) -> None:
    output_dir = Path(args.output_dir).resolve()
    plan = _read_json(output_dir / "plan.json")
    if plan.get("experiment_version") != CONTRIBUTION_POPULATION_VERSION:
        raise ValueError("population aggregate requires a v5 plan")
    rows = [
        item
        for seed in plan["probe_seeds"]
        for item in _load_jsonl(output_dir / "workers" / f"seed_{seed}.jsonl")
    ]
    expected = len(plan["jobs"]) * len(plan["probe_seeds"])
    if len(rows) != expected:
        raise ValueError(f"Probe matrix is incomplete: {len(rows)} != {expected}")
    if {item["plan_hash"] for item in rows} != {plan["plan_hash"]}:
        raise ValueError("Probe rows cross frozen plan identities")
    if {item["experiment_version"] for item in rows} != {plan["experiment_version"]}:
        raise ValueError("Probe rows cross experiment versions")
    by_key = {(item["task_id"], item["state_id"], item["seed"]): item for item in rows}
    if len(by_key) != len(rows):
        raise ValueError("Probe matrix contains duplicate task/state/seed rows")
    estimation_seeds = set(plan["estimation_seeds"])
    validation_seeds = set(plan["validation_seeds"])
    by_task_state: defaultdict[tuple[str, str], list[dict[str, Any]]] = defaultdict(list)
    for row in rows:
        by_task_state[(row["task_id"], row["state_id"])].append(row)
    state_rows = []
    for (task_id, state_id), values in sorted(by_task_state.items()):
        estimation = [
            item["performance_gain"] for item in values if item["seed"] in estimation_seeds
        ]
        validation = [
            item["performance_gain"] for item in values if item["seed"] in validation_seeds
        ]
        representative = values[0]
        state_rows.append(
            {
                "task_id": task_id,
                "task_type": representative["task_type"],
                "state_id": state_id,
                "strategy": representative["strategy"],
                "estimation_mean_gain": statistics.fmean(estimation),
                "validation_mean_gain": statistics.fmean(validation),
                "estimation_seed_gains": estimation,
                "validation_seed_gains": validation,
            }
        )
    grouped: defaultdict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in state_rows:
        grouped[row["task_id"]].append(row)
    task_rows = []
    for task_id, values in sorted(grouped.items()):
        values.sort(key=lambda item: item["state_id"])
        penalty_coefficient = float(plan["uncertainty_penalty_coefficient"])
        state_probabilities = _current_state_probabilities(
            values,
            policy=str(plan["state_probability_policy"]),
        )
        _attach_contribution_signals(
            values,
            split="estimation",
            penalty_coefficient=penalty_coefficient,
            state_probabilities=state_probabilities,
        )
        _attach_contribution_signals(
            values,
            split="validation",
            penalty_coefficient=penalty_coefficient,
            state_probabilities=state_probabilities,
        )
        for row in values:
            row["all_seed_seed_gains"] = row["estimation_seed_gains"] + row["validation_seed_gains"]
            row["all_seed_mean_gain"] = statistics.fmean(row["all_seed_seed_gains"])
        _attach_contribution_signals(
            values,
            split="all_seed",
            penalty_coefficient=penalty_coefficient,
            state_probabilities=state_probabilities,
        )
        estimated = [item["estimation_conservative_centered_contribution"] for item in values]
        validated = [item["validation_conservative_centered_contribution"] for item in values]
        raw_estimated = [item["estimation_centered_contribution"] for item in values]
        raw_validated = [item["validation_centered_contribution"] for item in values]
        task_rows.append(
            {
                "task_id": task_id,
                "task_type": values[0]["task_type"],
                "state_count": len(values),
                "current_distribution_hash": _current_distribution_hash(
                    task_id,
                    state_probabilities,
                ),
                "weighted_centered_means": {
                    split: sum(
                        state_probabilities[str(item["state_id"])]
                        * float(item[f"{split}_centered_contribution"])
                        for item in values
                    )
                    for split in ("estimation", "validation", "all_seed")
                },
                "weighted_conservative_centered_means": {
                    split: sum(
                        state_probabilities[str(item["state_id"])]
                        * float(item[f"{split}_conservative_centered_contribution"])
                        for item in values
                    )
                    for split in ("estimation", "validation", "all_seed")
                },
                "spearman": _spearman(estimated, validated),
                "pairwise_concordance": _pairwise_concordance(estimated, validated),
                "raw_centered_spearman": _spearman(raw_estimated, raw_validated),
                "raw_centered_pairwise_concordance": _pairwise_concordance(
                    raw_estimated,
                    raw_validated,
                ),
            }
        )
    spearman_values = [item["spearman"] for item in task_rows]
    concordance_values = [item["pairwise_concordance"] for item in task_rows]
    raw_spearman_values = [item["raw_centered_spearman"] for item in task_rows]
    raw_concordance_values = [item["raw_centered_pairwise_concordance"] for item in task_rows]
    sensitivity_rows = _penalty_sensitivity_rows(grouped)
    diagnostic_best = max(
        sensitivity_rows,
        key=lambda item: (
            item["macro_task_spearman"],
            item["macro_pairwise_concordance"],
            -abs(item["penalty_coefficient"] - float(plan["uncertainty_penalty_coefficient"])),
        ),
    )
    strategy_values: defaultdict[str, list[float]] = defaultdict(list)
    for row in state_rows:
        strategy_values[row["strategy"]].append(
            row["validation_conservative_centered_contribution"]
        )
    task_distribution_hashes = {
        str(row["task_id"]): str(row["current_distribution_hash"]) for row in task_rows
    }
    current_distribution_contract_hash = contribution_distribution_contract_hash(
        task_distribution_hashes
    )
    report: dict[str, Any] = {
        "experiment_version": plan["experiment_version"],
        "plan_hash": plan["plan_hash"],
        "probe_estimand_id": plan.get("probe_estimand_id"),
        "probe_step_count": plan["probe_step_count"],
        "learning_rate": plan["learning_rate"],
        "probe_optimizer": plan["probe_optimizer"],
        "probe_usage_scope": plan["probe_usage_scope"],
        "uncertainty_statistic": plan["uncertainty_statistic"],
        "uncertainty_penalty_coefficient": plan["uncertainty_penalty_coefficient"],
        "centering_policy": plan["centering_policy"],
        "state_probability_policy": plan["state_probability_policy"],
        "task_distribution_hashes": task_distribution_hashes,
        "current_distribution_contract_hash": current_distribution_contract_hash,
        "weighted_centering_replay_passed": True,
        "production_contribution_field": PRODUCTION_CONTRIBUTION_FIELD,
        "penalty_sensitivity_role": "internal_validation_diagnostic_only",
        "penalty_sensitivity_rows": sensitivity_rows,
        "diagnostic_best_penalty_coefficient": diagnostic_best["penalty_coefficient"],
        "evaluation_role": "internal_validation",
        "internal_validation_set_id": plan.get("internal_validation_set_id"),
        "final_test_set_id": plan.get("final_test_set_id"),
        "task_count": len(task_rows),
        "state_count": len(state_rows),
        "observation_count": len(rows),
        "seed_count": len(plan["probe_seeds"]),
        "seed_replicates_per_split": plan["seed_replicates_per_split"],
        "estimation_seeds": plan["estimation_seeds"],
        "validation_seeds": plan["validation_seeds"],
        "macro_task_spearman": statistics.fmean(spearman_values),
        "macro_task_spearman_ci95": _cluster_bootstrap_interval(
            spearman_values,
            samples=2000,
            seed=20260802,
        ),
        "macro_pairwise_concordance": statistics.fmean(concordance_values),
        "macro_pairwise_concordance_ci95": _cluster_bootstrap_interval(
            concordance_values,
            samples=2000,
            seed=20260803,
        ),
        "raw_centered_macro_task_spearman": statistics.fmean(raw_spearman_values),
        "raw_centered_macro_pairwise_concordance": statistics.fmean(raw_concordance_values),
        "conservative_minus_raw_spearman": (
            statistics.fmean(spearman_values) - statistics.fmean(raw_spearman_values)
        ),
        "conservative_minus_raw_pairwise_concordance": (
            statistics.fmean(concordance_values) - statistics.fmean(raw_concordance_values)
        ),
        "strategy_validation_mean_gain": {
            strategy: statistics.fmean(values)
            for strategy, values in sorted(strategy_values.items())
        },
        "task_rows": task_rows,
        "state_rows": state_rows,
        "status": "partial",
        "claim_boundary": (
            "Multi-task seed-disjoint local-Probe stability only. The report does not "
            "establish agreement with independent finite Interventions or Student gains."
        ),
        "target_population_validation_task_count": 30,
        "population_validation_gap": max(30 - len(task_rows), 0),
    }
    report["report_hash"] = canonical_hash(
        report,
        prefix="finance_contribution_population_report:",
    )
    _write_json(output_dir / "report.json", report)
    print(json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True))


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Run the Phase 1.1 multi-task Contribution Probe stability pilot"
    )
    subparsers = parser.add_subparsers(dest="command", required=True)
    prepare_parser = subparsers.add_parser("prepare")
    prepare_parser.add_argument("--artifacts-path", required=True)
    prepare_parser.add_argument("--source-probe-plan", required=True)
    prepare_parser.add_argument("--source-baseline-report", required=True)
    prepare_parser.add_argument("--output-dir", required=True)
    prepare_parser.add_argument("--task-count", type=int, default=10)
    prepare_parser.add_argument("--probe-step-count", type=int, default=3)
    prepare_parser.add_argument(
        "--run-role",
        required=True,
        choices=PROBE_RUN_ROLES,
    )
    prepare_parser.add_argument("--learning-rate", type=float, default=0.0002)
    prepare_parser.add_argument(
        "--uncertainty-penalty-coefficient",
        type=float,
        default=1.0,
    )
    prepare_parser.add_argument(
        "--probe-seeds",
        type=int,
        nargs="+",
        default=(
            20260811,
            20260812,
            20260813,
            20260814,
            20260821,
            20260822,
            20260823,
            20260824,
        ),
    )
    prepare_parser.set_defaults(handler=prepare)

    run_parser = subparsers.add_parser("run")
    run_parser.add_argument("--output-dir", required=True)
    run_parser.add_argument(
        "--gpu-ids",
        type=int,
        nargs="+",
        default=(3, 4, 5, 6),
    )
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
