from __future__ import annotations

import argparse
import gc
import hashlib
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

from trusted_synthesis.core.vtdo import (
    contribution_current_distribution_hash,
    contribution_distribution_contract_hash,
)
from trusted_synthesis.experiments.vtdo_experiment.contribution_validation import (
    _cluster_bootstrap_interval,
    _spearman,
)
from trusted_synthesis.experiments.vtdo_experiment.multistate import (
    AcceptedFinanceState,
    FinanceTaskStateArtifact,
    LineageStrategy,
    load_finance_multi_state_artifacts,
)
from trusted_synthesis.experiments.vtdo_experiment.phase1_contribution_population import (
    PENALTY_SENSITIVITY_GRID,
    _pairwise_concordance,
)
from trusted_synthesis.experiments.vtdo_experiment.phase1_probe_gpu import (
    MAX_SEQUENCE_LENGTH,
    _adapter_tensor_sha256,
    _baseline_lora_model,
    _batch,
    _encode_record,
    _load_records,
    _load_tokenizer,
    _read_json,
    _record_from_state,
    _seed_everything,
    _write_json,
)
from trusted_synthesis.experiments.vtdo_experiment.schema import VTDOTrainingRecord
from trusted_synthesis.hashing import canonical_hash

GRADIENT_ALIGNMENT_VERSION = "finance_contribution_gradient_projection.v1"
GRADIENT_PARAMETER_SPACE = "beneficiary_trainable_lora_parameters"
GRADIENT_SIGNAL = "objective_update_cosine_alignment"
GRADIENT_REPLICATE_KIND = "independent_evaluation_record"
GRADIENT_STATE_COUNT = 3
GRADIENT_STATE_STRATEGY_PRIORITY: tuple[LineageStrategy, ...] = (
    "compact_direct",
    "broad_direct",
    "broad_full_lineage",
    "compact_verify_frontier",
    "compact_output_lineage",
)
STATE_PROBABILITY_POLICY = "uniform_over_task_adaptive_three_verified_states_v1"
PRODUCTION_MINIMUM_TASK_COUNT = 30
PRODUCTION_MINIMUM_RECORDS_PER_SPLIT = 4
RUN_ROLES = ("smoke", "production_candidate")


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


def _valid_hashed_row(row: dict[str, Any], *, prefix: str) -> bool:
    expected = row.get("result_hash")
    if not isinstance(expected, str) or not expected:
        return False
    payload = dict(row)
    payload.pop("result_hash", None)
    return canonical_hash(payload, prefix=prefix) == expected


def _validate_run_contract(
    *,
    run_role: str,
    task_count: int,
    evaluation_record_count: int,
) -> None:
    if run_role not in RUN_ROLES:
        raise ValueError("unknown Gradient Projection run role")
    if task_count < 1:
        raise ValueError("Gradient Projection requires at least one task")
    if evaluation_record_count < 2 * PRODUCTION_MINIMUM_RECORDS_PER_SPLIT:
        raise ValueError("Gradient Projection requires at least eight evaluation records")
    if evaluation_record_count % 2:
        raise ValueError("Gradient Projection evaluation support must split evenly")
    if run_role == "production_candidate" and task_count < PRODUCTION_MINIMUM_TASK_COUNT:
        raise ValueError("production Gradient Projection requires at least 30 tasks")


def _selected_gradient_states(
    artifact: FinanceTaskStateArtifact,
) -> tuple[AcceptedFinanceState, ...]:
    """Freeze three verified quotient states from each task-specific support."""

    by_strategy = {item.strategy: item for item in artifact.accepted_states}
    selected = tuple(
        by_strategy[strategy]
        for strategy in GRADIENT_STATE_STRATEGY_PRIORITY
        if strategy in by_strategy
    )[:GRADIENT_STATE_COUNT]
    if len(selected) != GRADIENT_STATE_COUNT:
        raise ValueError(
            "Gradient Projection requires three independently verified states per task"
        )
    state_ids = tuple(item.assignment.state.state_id for item in selected)
    if len(set(state_ids)) != len(state_ids):
        raise ValueError("Gradient Projection selected duplicate quotient states")
    return selected


def _select_gradient_tasks(
    artifacts: tuple[FinanceTaskStateArtifact, ...],
    *,
    count: int,
    excluded_task_ids: set[str],
) -> tuple[FinanceTaskStateArtifact, ...]:
    groups: defaultdict[str, list[FinanceTaskStateArtifact]] = defaultdict(list)
    for artifact in artifacts:
        if artifact.omega.task.task_id in excluded_task_ids:
            continue
        try:
            _selected_gradient_states(artifact)
        except ValueError:
            continue
        groups[artifact.omega.task.public.task_type].append(artifact)
    for values in groups.values():
        values.sort(
            key=lambda item: (
                sum(
                    len(state.trajectory.model_dump_json())
                    for state in _selected_gradient_states(item)
                ),
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


def _gradient_parameter_manifest(model: Any) -> tuple[dict[str, Any], str]:
    parameters = {
        name: parameter
        for name, parameter in sorted(model.named_parameters())
        if parameter.requires_grad
    }
    if not parameters:
        raise ValueError("Gradient Projection found no trainable beneficiary parameters")
    manifest = {
        name: {
            "shape": list(parameter.shape),
            "dtype": str(parameter.dtype),
            "numel": parameter.numel(),
        }
        for name, parameter in parameters.items()
    }
    return manifest, canonical_hash(manifest, prefix="gradient_parameter_manifest:")


def _record_gradient(
    model: Any,
    tokenizer: Any,
    record: VTDOTrainingRecord,
) -> tuple[dict[str, Any], float, int]:
    import torch

    model.train()
    model.zero_grad(set_to_none=True)
    batch, supervised_tokens = _batch(tokenizer, record)
    output = model(**batch)
    loss = output.loss
    if not torch.isfinite(loss):
        raise ValueError("Gradient Projection produced a non-finite loss")
    loss.backward()
    gradients: dict[str, Any] = {}
    for name, parameter in sorted(model.named_parameters()):
        if not parameter.requires_grad:
            continue
        if parameter.grad is None:
            raise ValueError(f"Gradient Projection produced a missing gradient:{name}")
        gradient = parameter.grad.detach().float().cpu().contiguous()
        if not torch.isfinite(gradient).all():
            raise ValueError(f"Gradient Projection produced a non-finite gradient:{name}")
        gradients[name] = gradient
    loss_value = float(loss.detach().float().cpu())
    del output, loss, batch
    return gradients, loss_value, supervised_tokens


def _gradient_norm(gradients: dict[str, Any]) -> float:
    import torch

    reference = next(iter(gradients.values()))
    squared = torch.zeros((), dtype=torch.float64, device=reference.device)
    for gradient in gradients.values():
        squared += torch.sum(gradient.double() * gradient.double())
    value = math.sqrt(float(squared))
    if not value > 0 or not math.isfinite(value):
        raise ValueError("Gradient Projection encountered a zero or non-finite gradient norm")
    return value


def _weighted_gradient(
    gradients: list[dict[str, Any]],
    weights: list[float],
) -> dict[str, Any]:
    if not gradients or len(gradients) != len(weights):
        raise ValueError("weighted gradient inputs are incomplete")
    if any(weight <= 0 or not math.isfinite(weight) for weight in weights):
        raise ValueError("weighted gradient requires finite positive weights")
    normalizer = sum(weights)
    names = tuple(gradients[0])
    if any(tuple(item) != names for item in gradients):
        raise ValueError("gradient parameter manifests do not align")
    values: dict[str, Any] = {}
    for name in names:
        aggregate = gradients[0][name].new_zeros(gradients[0][name].shape)
        for gradient, weight in zip(gradients, weights, strict=True):
            aggregate.add_(gradient[name], alpha=weight / normalizer)
        values[name] = aggregate.contiguous()
    return values


def _gradient_dot(
    left: dict[str, Any],
    right: dict[str, Any],
) -> float:
    import torch

    if tuple(left) != tuple(right):
        raise ValueError("gradient projection parameter manifests differ")
    reference = next(iter(left.values()))
    dot = torch.zeros((), dtype=torch.float64, device=reference.device)
    for name in left:
        if left[name].device != right[name].device:
            raise ValueError("gradient projection tensors must share a device")
        left_value = left[name].double()
        right_value = right[name].double()
        dot += torch.sum(left_value * right_value)
    return float(dot)


def _normalized_gradient_alignment(
    left: dict[str, Any],
    right: dict[str, Any],
    *,
    left_norm: float,
    right_norm: float,
) -> tuple[float, float]:
    if not left_norm > 0 or not right_norm > 0:
        raise ValueError("gradient projection requires nonzero gradients")
    dot_value = _gradient_dot(left, right)
    cosine = dot_value / (left_norm * right_norm)
    if not -1.000001 <= cosine <= 1.000001 or not math.isfinite(cosine):
        raise ValueError("gradient cosine is outside its numeric contract")
    return dot_value, max(-1.0, min(1.0, cosine))


def _gradient_alignment(
    left: dict[str, Any],
    right: dict[str, Any],
) -> tuple[float, float, float, float]:
    left_norm = _gradient_norm(left)
    right_norm = _gradient_norm(right)
    dot, cosine = _normalized_gradient_alignment(
        left,
        right,
        left_norm=left_norm,
        right_norm=right_norm,
    )
    return dot, cosine, left_norm, right_norm


def _current_state_probabilities(state_ids: list[str]) -> dict[str, float]:
    if not state_ids or len(state_ids) != len(set(state_ids)):
        raise ValueError("Gradient Projection requires unique non-empty states")
    probability = 1.0 / len(state_ids)
    return {state_id: probability for state_id in sorted(state_ids)}


def _attach_centered_signal(
    rows: list[dict[str, Any]],
    *,
    split: str,
    penalty_coefficient: float,
    probabilities: dict[str, float],
) -> None:
    signal_field = f"{split}_aggregate_alignment"
    replicates_field = f"{split}_record_alignments"
    raw_centered_field = f"{split}_centered_contribution"
    deviation_field = f"{split}_sample_standard_deviation"
    conservative_raw_field = f"{split}_conservative_raw_contribution"
    conservative_centered_field = f"{split}_conservative_centered_contribution"
    raw_mean = sum(probabilities[str(row["state_id"])] * float(row[signal_field]) for row in rows)
    for row in rows:
        replicates = [float(value) for value in row[replicates_field]]
        if len(replicates) < PRODUCTION_MINIMUM_RECORDS_PER_SPLIT:
            raise ValueError("Gradient Projection has too few evaluation replicates")
        deviation = statistics.stdev(replicates)
        row["current_probability"] = probabilities[str(row["state_id"])]
        row[deviation_field] = deviation
        row[raw_centered_field] = float(row[signal_field]) - raw_mean
        row[conservative_raw_field] = float(row[signal_field]) - penalty_coefficient * deviation
    conservative_mean = sum(
        probabilities[str(row["state_id"])] * float(row[conservative_raw_field]) for row in rows
    )
    for row in rows:
        row[conservative_centered_field] = float(row[conservative_raw_field]) - conservative_mean
    for field in (raw_centered_field, conservative_centered_field):
        weighted_mean = sum(probabilities[str(row["state_id"])] * float(row[field]) for row in rows)
        if not math.isclose(weighted_mean, 0.0, abs_tol=1e-12):
            raise ValueError(f"Gradient Projection signal is not pi_t centered:{field}")


def _winner(values: list[float], state_ids: list[str]) -> str:
    if len(values) != len(state_ids) or not values:
        raise ValueError("winner calculation received incomplete states")
    return max(zip(values, state_ids, strict=True), key=lambda item: (item[0], item[1]))[1]


def _permutation_p_value(
    vectors: list[tuple[list[float], list[float]]],
    *,
    statistic: str,
    iterations: int,
    seed: int,
) -> float:
    import random

    if statistic not in {"spearman", "concordance"}:
        raise ValueError("unknown permutation statistic")
    observed = statistics.fmean(
        _spearman(left, right) if statistic == "spearman" else _pairwise_concordance(left, right)
        for left, right in vectors
    )
    rng = random.Random(seed)
    exceed = 0
    for _ in range(iterations):
        values = []
        for left, right in vectors:
            shuffled = list(left)
            rng.shuffle(shuffled)
            values.append(
                _spearman(shuffled, right)
                if statistic == "spearman"
                else _pairwise_concordance(shuffled, right)
            )
        exceed += int(statistics.fmean(values) >= observed)
    return (1 + exceed) / (iterations + 1)


def prepare(args: argparse.Namespace) -> None:
    support_dir = Path(args.source_support_dir).resolve()
    support_plan_path = support_dir / "plan.json"
    support_report_path = support_dir / "beneficiary_evaluation_report.json"
    support_plan = _read_json(support_plan_path)
    support_report = _read_json(support_report_path)
    if support_report.get("plan_hash") != support_plan.get("plan_hash"):
        raise ValueError("Gradient Projection support report does not replay its plan")
    evaluation_ids = tuple(support_plan["internal_validation_record_ids"])
    _validate_run_contract(
        run_role=args.run_role,
        task_count=args.task_count,
        evaluation_record_count=len(evaluation_ids),
    )
    if args.uncertainty_penalty_coefficient <= 0:
        raise ValueError("Gradient Projection uncertainty penalty must be positive")
    output_dir = Path(args.output_dir).resolve()
    output_dir.mkdir(parents=True, exist_ok=True)
    artifacts_path = Path(args.artifacts_path).resolve()
    artifacts = load_finance_multi_state_artifacts(artifacts_path)
    excluded_task_ids = set(str(value) for value in support_plan["additional_excluded_task_ids"])
    selected = _select_gradient_tasks(
        artifacts,
        count=args.task_count,
        excluded_task_ids=excluded_task_ids,
    )
    jobs: list[dict[str, Any]] = []
    target_records: list[VTDOTrainingRecord] = []
    for artifact in selected:
        for state in _selected_gradient_states(artifact):
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
                        prefix="gradient_projection_job:",
                    ),
                    "task_id": artifact.omega.task.task_id,
                    "task_type": artifact.omega.task.public.task_type,
                    "state_id": state.assignment.state.state_id,
                    "strategy": state.strategy,
                    "record_id": record.record_id,
                }
            )
    target_records_path = output_dir / "target_records.jsonl"
    target_records_path.write_text(
        "".join(record.model_dump_json() + "\n" for record in target_records),
        encoding="utf-8",
    )
    split_index = len(evaluation_ids) // 2
    source_records_path = Path(support_plan["records_path"]).resolve()
    source_records = _load_records(source_records_path)
    tokenizer = _load_tokenizer(Path(support_plan["model_dir"]))
    token_audit: dict[str, dict[str, int]] = {}
    for record in target_records:
        encoded = _encode_record(tokenizer, record, MAX_SEQUENCE_LENGTH)
        token_audit[record.record_id] = {
            "processed_tokens": len(encoded["input_ids"]),
            "prompt_tokens": int(encoded["prompt_tokens"]),
            "supervised_tokens": int(encoded["supervised_tokens"]),
        }
    for record_id in evaluation_ids:
        encoded = _encode_record(tokenizer, source_records[record_id], MAX_SEQUENCE_LENGTH)
        token_audit[record_id] = {
            "processed_tokens": len(encoded["input_ids"]),
            "prompt_tokens": int(encoded["prompt_tokens"]),
            "supervised_tokens": int(encoded["supervised_tokens"]),
        }
    values: dict[str, Any] = {
        "experiment_version": GRADIENT_ALIGNMENT_VERSION,
        "run_role": args.run_role,
        "artifacts_path": str(artifacts_path),
        "source_support_plan_path": str(support_plan_path),
        "source_support_plan_hash": support_plan["plan_hash"],
        "source_support_report_path": str(support_report_path),
        "source_support_report_hash": support_report["report_hash"],
        "source_records_path": str(source_records_path),
        "source_records_sha256": _sha256(source_records_path),
        "target_records_path": str(target_records_path),
        "target_records_sha256": _sha256(target_records_path),
        "model_dir": support_plan["model_dir"],
        "base_model_manifest_hash": support_plan["base_model_manifest_hash"],
        "beneficiary_adapter_dir": support_plan["beneficiary_adapter_dir"],
        "beneficiary_adapter_tensor_sha256": support_plan["beneficiary_adapter_tensor_sha256"],
        "beneficiary_model_state_id": support_plan["beneficiary_model_state_id"],
        "beneficiary_checkpoint_hash": support_plan["beneficiary_checkpoint_hash"],
        "selected_task_ids": tuple(item.omega.task.task_id for item in selected),
        "excluded_task_ids": tuple(sorted(excluded_task_ids)),
        "task_count": len(selected),
        "jobs": jobs,
        "state_count": len(jobs),
        "gradient_estimation_record_ids": evaluation_ids[:split_index],
        "gradient_validation_record_ids": evaluation_ids[split_index:],
        "final_test_record_ids": tuple(support_plan["final_test_record_ids"]),
        "gradient_estimation_set_id": canonical_hash(
            evaluation_ids[:split_index],
            prefix="gradient_projection_estimation_set:",
        ),
        "gradient_validation_set_id": canonical_hash(
            evaluation_ids[split_index:],
            prefix="gradient_projection_validation_set:",
        ),
        "final_test_set_id": support_plan["final_test_set_id"],
        "gradient_parameter_space": GRADIENT_PARAMETER_SPACE,
        "gradient_signal": GRADIENT_SIGNAL,
        "gradient_replicate_kind": GRADIENT_REPLICATE_KIND,
        "loss_function": "supervised_token_mean_nll",
        "objective_function": "negative_supervised_token_nll",
        "update_direction": "negative_training_loss_gradient",
        "sign_convention": (
            "cos(-grad_train_loss, grad(-validation_loss)) equals "
            "cos(grad_train_loss, grad_validation_loss); positive predicts improvement"
        ),
        "aggregate_gradient_weighting": "supervised_token_count",
        "uncertainty_statistic": "sample_standard_deviation_across_evaluation_records",
        "uncertainty_penalty_coefficient": args.uncertainty_penalty_coefficient,
        "centering_policy": "pi_weighted_after_uncertainty_penalty",
        "state_probability_policy": STATE_PROBABILITY_POLICY,
        "selected_state_count_per_task": GRADIENT_STATE_COUNT,
        "selected_state_strategy_priority": GRADIENT_STATE_STRATEGY_PRIORITY,
        "maximum_sequence_length": MAX_SEQUENCE_LENGTH,
        "token_audit": token_audit,
        "numeric_policy": support_plan["numeric_policy"],
        "claim_boundary": (
            "Gradient Projection is an experimental first-order estimator. It cannot influence "
            "VTDO production updates until independent distribution-perturbation rank gates pass."
        ),
    }
    values["gradient_estimand_id"] = canonical_hash(
        {
            "beneficiary_checkpoint_hash": values["beneficiary_checkpoint_hash"],
            "gradient_estimation_set_id": values["gradient_estimation_set_id"],
            "gradient_validation_set_id": values["gradient_validation_set_id"],
            "gradient_parameter_space": values["gradient_parameter_space"],
            "gradient_signal": values["gradient_signal"],
            "loss_function": values["loss_function"],
            "objective_function": values["objective_function"],
            "aggregate_gradient_weighting": values["aggregate_gradient_weighting"],
            "uncertainty_penalty_coefficient": values["uncertainty_penalty_coefficient"],
            "state_probability_policy": values["state_probability_policy"],
            "selected_state_strategy_priority": values["selected_state_strategy_priority"],
        },
        prefix="finance_contribution_gradient_estimand:",
    )
    values["plan_hash"] = canonical_hash(
        values,
        prefix="finance_contribution_gradient_plan:",
    )
    _write_json(output_dir / "plan.json", values)
    print(json.dumps(values, ensure_ascii=False, indent=2, sort_keys=True))


def build_evaluation_gradients(args: argparse.Namespace) -> None:
    os.environ["CUDA_VISIBLE_DEVICES"] = str(args.gpu_id)
    import torch
    from safetensors.torch import save_file

    output_dir = Path(args.output_dir).resolve()
    plan = _read_json(output_dir / "plan.json")
    if plan.get("experiment_version") != GRADIENT_ALIGNMENT_VERSION:
        raise ValueError("evaluation gradients require a current Gradient Projection plan")
    if _sha256(Path(plan["source_records_path"])) != plan["source_records_sha256"]:
        raise ValueError("evaluation records changed after Gradient Projection planning")
    _seed_everything(args.numeric_seed)
    torch.cuda.reset_peak_memory_stats()
    tokenizer = _load_tokenizer(Path(plan["model_dir"]))
    model = _baseline_lora_model(
        Path(plan["model_dir"]),
        Path(plan["beneficiary_adapter_dir"]),
    )
    if _adapter_tensor_sha256(model) != plan["beneficiary_adapter_tensor_sha256"]:
        raise ValueError("Gradient Projection loaded another beneficiary Adapter")
    parameter_manifest, parameter_manifest_hash = _gradient_parameter_manifest(model)
    source_records = _load_records(Path(plan["source_records_path"]))
    gradient_dir = output_dir / "evaluation_gradients"
    gradient_dir.mkdir(parents=True, exist_ok=True)
    all_record_ids = (
        *plan["gradient_estimation_record_ids"],
        *plan["gradient_validation_record_ids"],
    )
    record_rows: list[dict[str, Any]] = []
    gradients_by_id: dict[str, dict[str, Any]] = {}
    started = time.monotonic()
    for index, record_id in enumerate(all_record_ids):
        gradients, loss, supervised_tokens = _record_gradient(
            model,
            tokenizer,
            source_records[record_id],
        )
        path = gradient_dir / f"record_{index:02d}.safetensors"
        save_file(gradients, path)
        gradients_by_id[record_id] = gradients
        record_rows.append(
            {
                "record_id": record_id,
                "file": str(path),
                "sha256": _sha256(path),
                "loss": loss,
                "supervised_tokens": supervised_tokens,
                "gradient_norm": _gradient_norm(gradients),
            }
        )
    aggregate_rows = []
    rows_by_id = {row["record_id"]: row for row in record_rows}
    for split in ("estimation", "validation"):
        record_ids = tuple(plan[f"gradient_{split}_record_ids"])
        weights = [float(rows_by_id[record_id]["supervised_tokens"]) for record_id in record_ids]
        aggregate = _weighted_gradient(
            [gradients_by_id[record_id] for record_id in record_ids],
            weights,
        )
        path = gradient_dir / f"{split}_aggregate.safetensors"
        save_file(aggregate, path)
        aggregate_rows.append(
            {
                "split": split,
                "record_ids": record_ids,
                "weights": weights,
                "file": str(path),
                "sha256": _sha256(path),
                "gradient_norm": _gradient_norm(aggregate),
            }
        )
    manifest: dict[str, Any] = {
        "experiment_version": GRADIENT_ALIGNMENT_VERSION,
        "plan_hash": plan["plan_hash"],
        "beneficiary_checkpoint_hash": plan["beneficiary_checkpoint_hash"],
        "beneficiary_adapter_tensor_sha256": plan["beneficiary_adapter_tensor_sha256"],
        "gradient_parameter_space": plan["gradient_parameter_space"],
        "parameter_manifest": parameter_manifest,
        "parameter_manifest_hash": parameter_manifest_hash,
        "record_gradients": record_rows,
        "aggregate_gradients": aggregate_rows,
        "numeric_seed": args.numeric_seed,
        "runtime_seconds": time.monotonic() - started,
        "peak_gpu_memory_bytes": int(torch.cuda.max_memory_allocated()),
        "gpu_name": torch.cuda.get_device_name(0),
        "torch_version": torch.__version__,
    }
    manifest["manifest_hash"] = canonical_hash(
        manifest,
        prefix="finance_contribution_evaluation_gradient_manifest:",
    )
    _write_json(output_dir / "evaluation_gradient_manifest.json", manifest)
    print(json.dumps(manifest, ensure_ascii=False, indent=2, sort_keys=True))
    del model, gradients_by_id
    gc.collect()
    torch.cuda.empty_cache()


def _load_verified_gradient(path: Path, sha256: str) -> dict[str, Any]:
    from safetensors.torch import load_file

    if not path.is_file() or _sha256(path) != sha256:
        raise ValueError(f"frozen gradient artifact failed integrity replay:{path}")
    return load_file(path, device="cpu")


def _freeze_distribution_gradient_artifacts(
    output_dir: Path,
    grouped: dict[str, list[dict[str, Any]]],
) -> tuple[list[dict[str, Any]], dict[str, Any], dict[str, float]]:
    from safetensors.torch import save_file

    if not grouped:
        raise ValueError("cannot freeze an empty distribution gradient")
    task_dir = output_dir / "task_gradients"
    task_dir.mkdir(parents=True, exist_ok=True)
    task_marginal = 1.0 / len(grouped)
    task_marginals = {task_id: task_marginal for task_id in sorted(grouped)}
    task_artifacts: list[dict[str, Any]] = []
    global_gradient: dict[str, Any] | None = None
    for task_id, rows in sorted(grouped.items()):
        ordered = sorted(rows, key=lambda row: str(row["state_id"]))
        probabilities = _current_state_probabilities([str(row["state_id"]) for row in ordered])
        state_gradients = [
            _load_verified_gradient(
                Path(str(row["state_gradient_file"])),
                str(row["state_gradient_sha256"]),
            )
            for row in ordered
        ]
        task_gradient = _weighted_gradient(
            state_gradients,
            [probabilities[str(row["state_id"])] for row in ordered],
        )
        task_key = hashlib.sha256(task_id.encode("utf-8")).hexdigest()[:24]
        path = task_dir / f"task_{task_key}.safetensors"
        save_file(task_gradient, path)
        task_artifacts.append(
            {
                "task_id": task_id,
                "current_probabilities": probabilities,
                "file": str(path),
                "sha256": _sha256(path),
                "gradient_norm": _gradient_norm(task_gradient),
            }
        )
        if global_gradient is None:
            global_gradient = {
                name: value.new_zeros(value.shape) for name, value in task_gradient.items()
            }
        for name, value in task_gradient.items():
            global_gradient[name].add_(value, alpha=task_marginal)
        del state_gradients, task_gradient
    if global_gradient is None:
        raise ValueError("global distribution gradient was not constructed")
    global_path = output_dir / "global_distribution_gradient.safetensors"
    save_file(global_gradient, global_path)
    global_artifact = {
        "task_marginal_policy": "uniform_over_selected_tasks",
        "task_marginals": task_marginals,
        "file": str(global_path),
        "sha256": _sha256(global_path),
        "gradient_norm": _gradient_norm(global_gradient),
    }
    return task_artifacts, global_artifact, task_marginals


def _load_gradient_artifacts(
    manifest: dict[str, Any],
    *,
    device: str = "cpu",
) -> tuple[dict[str, dict[str, Any]], dict[str, dict[str, Any]]]:
    from safetensors.torch import load_file

    record_gradients = {}
    for row in manifest["record_gradients"]:
        path = Path(row["file"])
        if _sha256(path) != row["sha256"]:
            raise ValueError("evaluation record gradient changed after freezing")
        record_gradients[str(row["record_id"])] = load_file(path, device=device)
    aggregate_gradients = {}
    for row in manifest["aggregate_gradients"]:
        path = Path(row["file"])
        if _sha256(path) != row["sha256"]:
            raise ValueError("aggregate evaluation gradient changed after freezing")
        aggregate_gradients[str(row["split"])] = load_file(path, device=device)
    return record_gradients, aggregate_gradients


def _worker(
    plan_path: str,
    *,
    gpu_id: int,
    partition_index: int,
    partition_count: int,
) -> dict[str, Any]:
    os.environ["CUDA_VISIBLE_DEVICES"] = str(gpu_id)
    import torch
    from safetensors.torch import save_file

    plan = _read_json(Path(plan_path))
    if plan.get("experiment_version") != GRADIENT_ALIGNMENT_VERSION:
        raise ValueError("Gradient Projection worker requires a current plan")
    output_dir = Path(plan_path).parent
    manifest = _read_json(output_dir / "evaluation_gradient_manifest.json")
    if manifest.get("plan_hash") != plan["plan_hash"]:
        raise ValueError("evaluation gradients belong to another plan")
    if _sha256(Path(plan["target_records_path"])) != plan["target_records_sha256"]:
        raise ValueError("target records changed after Gradient Projection planning")
    worker_path = output_dir / "workers" / f"partition_{partition_index}.jsonl"
    completed: set[str] = set()
    for row in _load_jsonl(worker_path):
        if row.get("status") != "passed":
            continue
        gradient_file = row.get("state_gradient_file")
        gradient_sha256 = row.get("state_gradient_sha256")
        valid = (
            isinstance(gradient_file, str)
            and isinstance(gradient_sha256, str)
            and _valid_hashed_row(row, prefix="finance_contribution_gradient_result:")
            and Path(gradient_file).is_file()
            and _sha256(Path(gradient_file)) == gradient_sha256
        )
        if not valid:
            raise ValueError("Gradient Projection resume artifact failed integrity replay")
        completed.add(str(row["job_id"]))
    jobs = [
        job for index, job in enumerate(plan["jobs"]) if index % partition_count == partition_index
    ]
    state_gradient_dir = output_dir / "state_gradients"
    state_gradient_dir.mkdir(parents=True, exist_ok=True)
    records = _load_records(Path(plan["target_records_path"]))
    _seed_everything(20260840 + partition_index)
    torch.cuda.reset_peak_memory_stats()
    tokenizer = _load_tokenizer(Path(plan["model_dir"]))
    model = _baseline_lora_model(
        Path(plan["model_dir"]),
        Path(plan["beneficiary_adapter_dir"]),
    )
    if _adapter_tensor_sha256(model) != plan["beneficiary_adapter_tensor_sha256"]:
        raise ValueError("Gradient Projection worker loaded another beneficiary Adapter")
    parameter_manifest, parameter_manifest_hash = _gradient_parameter_manifest(model)
    if parameter_manifest_hash != manifest["parameter_manifest_hash"]:
        raise ValueError("Gradient Projection parameter space changed after freezing")
    if parameter_manifest != manifest["parameter_manifest"]:
        raise ValueError("Gradient Projection parameter manifest failed exact replay")
    record_gradients, aggregate_gradients = _load_gradient_artifacts(
        manifest,
        device="cuda:0",
    )
    record_gradient_norms = {
        str(row["record_id"]): float(row["gradient_norm"])
        for row in manifest["record_gradients"]
    }
    aggregate_gradient_norms = {
        str(row["split"]): float(row["gradient_norm"])
        for row in manifest["aggregate_gradients"]
    }
    completed_now = 0
    started = time.monotonic()
    for job in jobs:
        if job["job_id"] in completed:
            continue
        state_gradient, state_loss, supervised_tokens = _record_gradient(
            model,
            tokenizer,
            records[job["record_id"]],
        )
        state_gradient_path = state_gradient_dir / f"{job['job_id']}.safetensors"
        save_file(state_gradient, state_gradient_path)
        state_gradient_sha256 = _sha256(state_gradient_path)
        state_gradient_for_alignment = {
            name: value.to(device="cuda:0", non_blocking=False)
            for name, value in state_gradient.items()
        }
        state_gradient_norm = _gradient_norm(state_gradient_for_alignment)
        split_rows: dict[str, dict[str, Any]] = {}
        for split in ("estimation", "validation"):
            record_ids = tuple(plan[f"gradient_{split}_record_ids"])
            record_alignments = []
            record_directional_dots = []
            for record_id in record_ids:
                dot, cosine = _normalized_gradient_alignment(
                    state_gradient_for_alignment,
                    record_gradients[record_id],
                    left_norm=state_gradient_norm,
                    right_norm=record_gradient_norms[record_id],
                )
                record_alignments.append(cosine)
                record_directional_dots.append(dot)
            objective_norm = aggregate_gradient_norms[split]
            aggregate_dot, aggregate_cosine = _normalized_gradient_alignment(
                state_gradient_for_alignment,
                aggregate_gradients[split],
                left_norm=state_gradient_norm,
                right_norm=objective_norm,
            )
            split_rows[split] = {
                "record_ids": record_ids,
                "record_alignments": record_alignments,
                "record_directional_dots": record_directional_dots,
                "aggregate_alignment": aggregate_cosine,
                "aggregate_directional_dot": aggregate_dot,
                "state_gradient_norm": state_gradient_norm,
                "objective_gradient_norm": objective_norm,
            }
        result = {
            **job,
            "experiment_version": GRADIENT_ALIGNMENT_VERSION,
            "plan_hash": plan["plan_hash"],
            "evaluation_gradient_manifest_hash": manifest["manifest_hash"],
            "gpu_id": gpu_id,
            "partition_index": partition_index,
            "partition_count": partition_count,
            "status": "passed",
            "state_loss": state_loss,
            "state_gradient_file": str(state_gradient_path),
            "state_gradient_sha256": state_gradient_sha256,
            "state_gradient_norm": state_gradient_norm,
            "state_supervised_tokens": supervised_tokens,
            "estimation_record_ids": split_rows["estimation"]["record_ids"],
            "estimation_record_alignments": split_rows["estimation"]["record_alignments"],
            "estimation_record_directional_dots": split_rows["estimation"][
                "record_directional_dots"
            ],
            "estimation_aggregate_alignment": split_rows["estimation"]["aggregate_alignment"],
            "estimation_aggregate_directional_dot": split_rows["estimation"][
                "aggregate_directional_dot"
            ],
            "validation_record_ids": split_rows["validation"]["record_ids"],
            "validation_record_alignments": split_rows["validation"]["record_alignments"],
            "validation_record_directional_dots": split_rows["validation"][
                "record_directional_dots"
            ],
            "validation_aggregate_alignment": split_rows["validation"]["aggregate_alignment"],
            "validation_aggregate_directional_dot": split_rows["validation"][
                "aggregate_directional_dot"
            ],
            "estimation_objective_gradient_norm": split_rows["estimation"][
                "objective_gradient_norm"
            ],
            "validation_objective_gradient_norm": split_rows["validation"][
                "objective_gradient_norm"
            ],
        }
        result["result_hash"] = canonical_hash(
            result,
            prefix="finance_contribution_gradient_result:",
        )
        _append_jsonl(worker_path, result)
        del state_gradient_for_alignment, state_gradient
        completed_now += 1
    report = {
        "gpu_id": gpu_id,
        "partition_index": partition_index,
        "partition_count": partition_count,
        "job_count": len(jobs),
        "completed_before_resume": len(completed),
        "completed_now": completed_now,
        "runtime_seconds": time.monotonic() - started,
        "peak_gpu_memory_bytes": int(torch.cuda.max_memory_allocated()),
    }
    del model, record_gradients, aggregate_gradients
    gc.collect()
    torch.cuda.empty_cache()
    return report


def run(args: argparse.Namespace) -> None:
    output_dir = Path(args.output_dir).resolve()
    plan_path = output_dir / "plan.json"
    plan = _read_json(plan_path)
    if not args.gpu_ids or len(set(args.gpu_ids)) != len(args.gpu_ids):
        raise ValueError("Gradient Projection requires unique GPU ids")
    partition_count = min(len(args.gpu_ids), len(plan["jobs"]))
    context = multiprocessing.get_context("spawn")
    reports = []
    with ProcessPoolExecutor(max_workers=partition_count, mp_context=context) as executor:
        futures = {
            executor.submit(
                _worker,
                str(plan_path),
                gpu_id=gpu_id,
                partition_index=index,
                partition_count=partition_count,
            ): (gpu_id, index)
            for index, gpu_id in enumerate(args.gpu_ids[:partition_count])
        }
        for future in as_completed(futures):
            reports.append(future.result())
    summary = {
        "plan_hash": plan["plan_hash"],
        "workers": sorted(reports, key=lambda item: item["partition_index"]),
    }
    _write_json(output_dir / "worker_summary.json", summary)
    print(json.dumps(summary, ensure_ascii=False, indent=2, sort_keys=True))


def aggregate(args: argparse.Namespace) -> None:
    output_dir = Path(args.output_dir).resolve()
    plan = _read_json(output_dir / "plan.json")
    manifest = _read_json(output_dir / "evaluation_gradient_manifest.json")
    rows = [
        row
        for path in sorted((output_dir / "workers").glob("*.jsonl"))
        for row in _load_jsonl(path)
    ]
    if len(rows) != len(plan["jobs"]):
        raise ValueError(f"Gradient Projection matrix is incomplete:{len(rows)}")
    if any(
        not _valid_hashed_row(row, prefix="finance_contribution_gradient_result:") for row in rows
    ):
        raise ValueError("Gradient Projection result identity failed replay")
    if any(
        not Path(str(row["state_gradient_file"])).is_file()
        or _sha256(Path(str(row["state_gradient_file"]))) != str(row["state_gradient_sha256"])
        for row in rows
    ):
        raise ValueError("Gradient Projection state gradient failed integrity replay")
    if {row["plan_hash"] for row in rows} != {plan["plan_hash"]}:
        raise ValueError("Gradient Projection rows cross plans")
    if {row["evaluation_gradient_manifest_hash"] for row in rows} != {manifest["manifest_hash"]}:
        raise ValueError("Gradient Projection rows cross evaluation gradients")
    by_key = {(row["task_id"], row["state_id"]): row for row in rows}
    if len(by_key) != len(rows):
        raise ValueError("Gradient Projection matrix contains duplicate task-state rows")
    grouped: defaultdict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in rows:
        grouped[str(row["task_id"])].append(row)
    task_rows = []
    task_vectors = []
    state_rows = []
    task_distribution_hashes = {}
    penalty = float(plan["uncertainty_penalty_coefficient"])
    for task_id, values in sorted(grouped.items()):
        values.sort(key=lambda row: str(row["state_id"]))
        probabilities = _current_state_probabilities([str(row["state_id"]) for row in values])
        _attach_centered_signal(
            values,
            split="estimation",
            penalty_coefficient=penalty,
            probabilities=probabilities,
        )
        _attach_centered_signal(
            values,
            split="validation",
            penalty_coefficient=penalty,
            probabilities=probabilities,
        )
        estimation = [float(row["estimation_conservative_centered_contribution"]) for row in values]
        validation = [float(row["validation_conservative_centered_contribution"]) for row in values]
        state_ids = [str(row["state_id"]) for row in values]
        distribution_hash = contribution_current_distribution_hash(task_id, probabilities)
        task_distribution_hashes[task_id] = distribution_hash
        task_rows.append(
            {
                "task_id": task_id,
                "task_type": values[0]["task_type"],
                "state_count": len(values),
                "current_distribution_hash": distribution_hash,
                "spearman": _spearman(estimation, validation),
                "pairwise_concordance": _pairwise_concordance(estimation, validation),
                "winner_agreement": float(
                    _winner(estimation, state_ids) == _winner(validation, state_ids)
                ),
            }
        )
        task_vectors.append((estimation, validation))
        state_rows.extend(values)
    task_gradient_artifacts, global_gradient_artifact, task_marginals = (
        _freeze_distribution_gradient_artifacts(output_dir, grouped)
    )
    distribution_gradient_manifest_hash = canonical_hash(
        {"tasks": task_gradient_artifacts, "global": global_gradient_artifact},
        prefix="finance_distribution_gradient_manifest:",
    )
    spearman_values = [float(row["spearman"]) for row in task_rows]
    concordance_values = [float(row["pairwise_concordance"]) for row in task_rows]
    winner_values = [float(row["winner_agreement"]) for row in task_rows]
    sensitivity_rows = []
    for coefficient in PENALTY_SENSITIVITY_GRID:
        task_spearman = []
        task_concordance = []
        for values in grouped.values():
            estimation = [
                float(row["estimation_aggregate_alignment"])
                - coefficient * statistics.stdev(row["estimation_record_alignments"])
                for row in values
            ]
            validation = [
                float(row["validation_aggregate_alignment"])
                - coefficient * statistics.stdev(row["validation_record_alignments"])
                for row in values
            ]
            task_spearman.append(_spearman(estimation, validation))
            task_concordance.append(_pairwise_concordance(estimation, validation))
        sensitivity_rows.append(
            {
                "penalty_coefficient": coefficient,
                "macro_task_spearman": statistics.fmean(task_spearman),
                "macro_pairwise_concordance": statistics.fmean(task_concordance),
            }
        )
    report: dict[str, Any] = {
        "experiment_version": GRADIENT_ALIGNMENT_VERSION,
        "plan_hash": plan["plan_hash"],
        "gradient_estimand_id": plan["gradient_estimand_id"],
        "evaluation_gradient_manifest_hash": manifest["manifest_hash"],
        "run_role": plan["run_role"],
        "gradient_parameter_space": plan["gradient_parameter_space"],
        "gradient_signal": plan["gradient_signal"],
        "gradient_replicate_kind": plan["gradient_replicate_kind"],
        "sign_convention": plan["sign_convention"],
        "gradient_estimation_set_id": plan["gradient_estimation_set_id"],
        "gradient_validation_set_id": plan["gradient_validation_set_id"],
        "final_test_set_id": plan["final_test_set_id"],
        "task_count": len(task_rows),
        "state_count": len(state_rows),
        "evaluation_records_per_split": len(plan["gradient_estimation_record_ids"]),
        "uncertainty_penalty_coefficient": penalty,
        "state_probability_policy": plan["state_probability_policy"],
        "task_distribution_hashes": task_distribution_hashes,
        "task_marginal_policy": "uniform_over_selected_tasks",
        "task_marginals": task_marginals,
        "task_gradient_artifacts": task_gradient_artifacts,
        "global_gradient_artifact": global_gradient_artifact,
        "distribution_gradient_manifest_hash": distribution_gradient_manifest_hash,
        "distribution_gradient_role": "exact_one_step_full_distribution_intervention_input",
        "current_distribution_contract_hash": contribution_distribution_contract_hash(
            task_distribution_hashes
        ),
        "macro_task_spearman": statistics.fmean(spearman_values),
        "macro_task_spearman_ci95": _cluster_bootstrap_interval(
            spearman_values,
            samples=5000,
            seed=20260841,
        ),
        "macro_pairwise_concordance": statistics.fmean(concordance_values),
        "macro_pairwise_concordance_ci95": _cluster_bootstrap_interval(
            concordance_values,
            samples=5000,
            seed=20260842,
        ),
        "winner_agreement_rate": statistics.fmean(winner_values),
        "macro_spearman_p_value": _permutation_p_value(
            task_vectors,
            statistic="spearman",
            iterations=10000,
            seed=20260843,
        ),
        "macro_pairwise_concordance_p_value": _permutation_p_value(
            task_vectors,
            statistic="concordance",
            iterations=10000,
            seed=20260844,
        ),
        "penalty_sensitivity_role": "diagnostic_only",
        "penalty_sensitivity_rows": sensitivity_rows,
        "task_rows": task_rows,
        "state_rows": state_rows,
        "status": "partial",
        "production_authorized": False,
        "blockers": ["independent_distribution_intervention_not_run"],
        "claim_boundary": plan["claim_boundary"],
    }
    report["report_hash"] = canonical_hash(
        report,
        prefix="finance_contribution_gradient_report:",
    )
    _write_json(output_dir / "report.json", report)
    print(json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True))


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Estimate VTDO Contribution with first-order Gradient Projection"
    )
    subparsers = parser.add_subparsers(dest="command", required=True)
    prepare_parser = subparsers.add_parser("prepare")
    prepare_parser.add_argument("--artifacts-path", required=True)
    prepare_parser.add_argument("--source-support-dir", required=True)
    prepare_parser.add_argument("--output-dir", required=True)
    prepare_parser.add_argument("--task-count", type=int, default=30)
    prepare_parser.add_argument("--run-role", choices=RUN_ROLES, required=True)
    prepare_parser.add_argument("--uncertainty-penalty-coefficient", type=float, default=1.0)
    prepare_parser.set_defaults(handler=prepare)
    gradients_parser = subparsers.add_parser("build-evaluation-gradients")
    gradients_parser.add_argument("--output-dir", required=True)
    gradients_parser.add_argument("--gpu-id", type=int, required=True)
    gradients_parser.add_argument("--numeric-seed", type=int, default=20260840)
    gradients_parser.set_defaults(handler=build_evaluation_gradients)
    run_parser = subparsers.add_parser("run")
    run_parser.add_argument("--output-dir", required=True)
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
