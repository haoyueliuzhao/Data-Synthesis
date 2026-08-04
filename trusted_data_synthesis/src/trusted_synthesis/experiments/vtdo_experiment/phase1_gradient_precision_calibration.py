from __future__ import annotations

import argparse
import gc
import json
import math
import multiprocessing
import os
import time
from concurrent.futures import ProcessPoolExecutor, as_completed
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, Literal

from trusted_synthesis.experiments.vtdo_experiment.phase1_contribution_gradient import (
    _activate_deterministic_eval_checkpointing,
    _collect_trainable_gradients,
    _gradient_alignment,
    _gradient_norm,
    _gradient_parameter_manifest,
    _load_gradient_artifacts,
    _supervised_causal_projection,
    _token_gradient_decomposition_metrics,
    _weighted_gradient,
)
from trusted_synthesis.experiments.vtdo_experiment.phase1_probe_gpu import (
    _adapter_tensor_sha256,
    _batch,
    _load_records,
    _load_tokenizer,
    _read_json,
    _seed_everything,
    _validated_hf_device_map,
    _write_json,
)
from trusted_synthesis.experiments.vtdo_experiment.schema import VTDOTrainingRecord
from trusted_synthesis.hashing import canonical_hash

CALIBRATION_VERSION = "finance_gradient_finite_precision_calibration.v3"
SOURCE_GRADIENT_VERSION = "finance_contribution_gradient_projection.v10"
SPLITS = ("development", "validation")
SHARD_MEMORY_CAP_GIB = 12


@dataclass(frozen=True)
class PrecisionProfile:
    profile_id: str
    model_dtype: Literal["bfloat16", "float32"]
    sparse_projection_dtype: Literal["model", "float32"]
    loss_accumulator_dtype: Literal["float32", "float64"]
    gradient_checkpointing: bool
    cuda_matmul_allow_tf32: bool
    float32_matmul_precision: Literal["highest", "high"]


PRECISION_PROFILES = (
    PrecisionProfile(
        profile_id="bf16_checkpoint_tf32_v10_control",
        model_dtype="bfloat16",
        sparse_projection_dtype="model",
        loss_accumulator_dtype="float32",
        gradient_checkpointing=True,
        cuda_matmul_allow_tf32=True,
        float32_matmul_precision="high",
    ),
    PrecisionProfile(
        profile_id="bf16_checkpoint_strict_accumulation",
        model_dtype="bfloat16",
        sparse_projection_dtype="float32",
        loss_accumulator_dtype="float64",
        gradient_checkpointing=True,
        cuda_matmul_allow_tf32=False,
        float32_matmul_precision="highest",
    ),
    PrecisionProfile(
        profile_id="bf16_no_checkpoint_strict_accumulation",
        model_dtype="bfloat16",
        sparse_projection_dtype="float32",
        loss_accumulator_dtype="float64",
        gradient_checkpointing=False,
        cuda_matmul_allow_tf32=False,
        float32_matmul_precision="highest",
    ),
    PrecisionProfile(
        profile_id="fp32_checkpoint_strict_accumulation",
        model_dtype="float32",
        sparse_projection_dtype="float32",
        loss_accumulator_dtype="float64",
        gradient_checkpointing=True,
        cuda_matmul_allow_tf32=False,
        float32_matmul_precision="highest",
    ),
)

# These thresholds are preregistered before the numerical development run. The
# old 1e-4 relative-error boundary is retained instead of being fit to v10.
CALIBRATION_THRESHOLDS = {
    "maximum_loss_identity_absolute_error": 1e-6,
    "minimum_gradient_recomposition_cosine": 0.9999,
    "maximum_gradient_recomposition_relative_error": 1e-4,
    "maximum_gp_score_absolute_delta": 1e-4,
    "minimum_task_rank_agreement": 1.0,
    "maximum_update_total_variation": 1e-4,
    "maximum_update_jensen_shannon": 1e-6,
}
DEVELOPMENT_SAFETY_BOUNDS = {
    "maximum_loss_identity_absolute_error": 1e-6,
    "minimum_gradient_recomposition_cosine": 0.999,
    "maximum_gradient_recomposition_relative_error": 0.03,
    "maximum_gp_score_absolute_delta": 0.005,
    "minimum_task_rank_agreement": 1.0,
    "maximum_update_total_variation": 0.001,
    "maximum_update_jensen_shannon": 1e-6,
}
THRESHOLD_CALIBRATION_RULE = {
    "maximum_loss_identity_absolute_error": {"fixed": 1e-6},
    "minimum_gradient_recomposition_cosine": {
        "development_margin": 0.0001,
        "quantization": 0.00001,
        "lower_bound": 0.999,
    },
    "maximum_gradient_recomposition_relative_error": {
        "development_multiplier": 1.25,
        "quantization": 0.001,
        "upper_bound": 0.03,
    },
    "maximum_gp_score_absolute_delta": {
        "development_multiplier": 1.5,
        "quantization": 0.0001,
        "upper_bound": 0.005,
    },
    "minimum_task_rank_agreement": {"fixed": 1.0},
    "maximum_update_total_variation": {
        "development_multiplier": 1.5,
        "quantization": 0.00001,
        "upper_bound": 0.001,
    },
    "maximum_update_jensen_shannon": {"fixed": 1e-6},
}


def _profile(profile_id: str) -> PrecisionProfile:
    matches = [profile for profile in PRECISION_PROFILES if profile.profile_id == profile_id]
    if len(matches) != 1:
        raise ValueError(f"unknown precision profile:{profile_id}")
    return matches[0]


def _development_eligible(metrics: dict[str, Any]) -> bool:
    return all(
        math.isfinite(float(metrics[name]))
        and (
            float(metrics[name]) >= threshold
            if name.startswith("minimum_")
            else float(metrics[name]) <= threshold
        )
        for name, threshold in DEVELOPMENT_SAFETY_BOUNDS.items()
    )


def _ceil_to(value: float, quantum: float) -> float:
    return math.ceil(value / quantum - 1e-12) * quantum


def _floor_to(value: float, quantum: float) -> float:
    return math.floor(value / quantum + 1e-12) * quantum


def _derive_validation_thresholds(metrics: dict[str, Any]) -> dict[str, float]:
    relative_rule = THRESHOLD_CALIBRATION_RULE[
        "maximum_gradient_recomposition_relative_error"
    ]
    score_rule = THRESHOLD_CALIBRATION_RULE["maximum_gp_score_absolute_delta"]
    tv_rule = THRESHOLD_CALIBRATION_RULE["maximum_update_total_variation"]
    cosine_rule = THRESHOLD_CALIBRATION_RULE["minimum_gradient_recomposition_cosine"]
    thresholds = {
        "maximum_loss_identity_absolute_error": 1e-6,
        "minimum_gradient_recomposition_cosine": max(
            float(cosine_rule["lower_bound"]),
            _floor_to(
                float(metrics["minimum_gradient_recomposition_cosine"])
                - float(cosine_rule["development_margin"]),
                float(cosine_rule["quantization"]),
            ),
        ),
        "maximum_gradient_recomposition_relative_error": min(
            float(relative_rule["upper_bound"]),
            _ceil_to(
                float(metrics["maximum_gradient_recomposition_relative_error"])
                * float(relative_rule["development_multiplier"]),
                float(relative_rule["quantization"]),
            ),
        ),
        "maximum_gp_score_absolute_delta": min(
            float(score_rule["upper_bound"]),
            _ceil_to(
                float(metrics["maximum_gp_score_absolute_delta"])
                * float(score_rule["development_multiplier"]),
                float(score_rule["quantization"]),
            ),
        ),
        "minimum_task_rank_agreement": 1.0,
        "maximum_update_total_variation": min(
            float(tv_rule["upper_bound"]),
            _ceil_to(
                float(metrics["maximum_update_total_variation"])
                * float(tv_rule["development_multiplier"]),
                float(tv_rule["quantization"]),
            ),
        ),
        "maximum_update_jensen_shannon": 1e-6,
    }
    if not all(
        (
            thresholds[name] >= bound
            if name.startswith("minimum_")
            else thresholds[name] <= bound
        )
        for name, bound in DEVELOPMENT_SAFETY_BOUNDS.items()
    ):
        raise ValueError("derived precision thresholds exceed preregistered safety bounds")
    return thresholds


def _sha256(path: Path) -> str:
    import hashlib

    digest = hashlib.sha256()
    with path.open("rb") as source:
        for chunk in iter(lambda: source.read(4 * 1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _configure_numeric_policy(profile: PrecisionProfile) -> None:
    import torch

    torch.set_float32_matmul_precision(profile.float32_matmul_precision)
    torch.backends.cuda.matmul.allow_tf32 = profile.cuda_matmul_allow_tf32
    torch.backends.cudnn.allow_tf32 = profile.cuda_matmul_allow_tf32


def _strict_max_memory(
    device_count: int,
    device_ids: tuple[int, ...],
    *,
    per_device_gib: int = SHARD_MEMORY_CAP_GIB,
) -> dict[int, int | str]:
    if (
        device_count <= 0
        or not device_ids
        or len(set(device_ids)) != len(device_ids)
        or any(device_id < 0 or device_id >= device_count for device_id in device_ids)
    ):
        raise ValueError("invalid precision calibration GPU whitelist")
    if per_device_gib <= 0:
        raise ValueError("precision calibration GPU memory cap must be positive")
    selected = set(device_ids)
    return {
        device_id: f"{per_device_gib}GiB" if device_id in selected else 0
        for device_id in range(device_count)
    }


def _load_calibration_model(
    *,
    model_dir: Path,
    adapter_dir: Path,
    profile: PrecisionProfile,
    gpu_ids: tuple[int, ...],
) -> tuple[Any, dict[str, str]]:
    import torch
    from peft import PeftModel
    from transformers import AutoModelForCausalLM

    dtype = torch.bfloat16 if profile.model_dtype == "bfloat16" else torch.float32
    load_kwargs: dict[str, Any] = {
        "local_files_only": True,
        "dtype": dtype,
        "attn_implementation": "sdpa",
        "low_cpu_mem_usage": True,
    }
    if len(gpu_ids) > 1:
        load_kwargs.update(
            {
                "device_map": "balanced",
                "max_memory": _strict_max_memory(
                    torch.cuda.device_count(),
                    gpu_ids,
                ),
            }
        )
    base = AutoModelForCausalLM.from_pretrained(model_dir, **load_kwargs)
    if len(gpu_ids) == 1:
        base = base.to(f"cuda:{gpu_ids[0]}")
        device_map = {"": str(gpu_ids[0])}
    else:
        device_map = _validated_hf_device_map(base, allowed_device_ids=gpu_ids)
    base.config.use_cache = False
    if profile.gradient_checkpointing:
        base.gradient_checkpointing_enable(
            gradient_checkpointing_kwargs={"use_reentrant": False}
        )
    else:
        base.gradient_checkpointing_disable()
    base.enable_input_require_grads()
    model = PeftModel.from_pretrained(base, adapter_dir, is_trainable=True)
    model.config.use_cache = False
    return model, device_map


def _sparse_logits(
    model: Any,
    batch: dict[str, Any],
    prediction_positions: Any,
    *,
    projection_dtype: Literal["model", "float32"],
) -> Any:
    import torch

    causal_model = model.get_base_model() if hasattr(model, "get_base_model") else model
    if not hasattr(causal_model, "get_decoder"):
        raise ValueError("precision calibration model does not expose a causal decoder")
    decoder_output = causal_model.get_decoder()(**batch, use_cache=False)
    hidden = decoder_output.last_hidden_state
    selected = hidden.index_select(1, prediction_positions.to(hidden.device))
    output_embedding = causal_model.get_output_embeddings()
    if output_embedding is None:
        raise ValueError("precision calibration model has no output embedding")
    selected = selected.to(output_embedding.weight.device)
    if projection_dtype == "model":
        return output_embedding(selected)
    bias = getattr(output_embedding, "bias", None)
    return torch.nn.functional.linear(
        selected.float(),
        output_embedding.weight.float(),
        None if bias is None else bias.float(),
    )


def _regional_loss(
    logits: Any,
    targets: Any,
    *,
    ordinals: Any | None,
    accumulator_dtype: Literal["float32", "float64"],
) -> Any:
    import torch

    if ordinals is not None:
        logits = logits.index_select(1, ordinals.to(logits.device))
        targets = targets.index_select(1, ordinals.to(targets.device))
    losses = torch.nn.functional.cross_entropy(
        logits.float().reshape(-1, logits.shape[-1]),
        targets.to(logits.device).reshape(-1),
        reduction="none",
    )
    if accumulator_dtype == "float64":
        return losses.double().mean()
    return losses.mean()


def _gradient_decomposition(
    model: Any,
    tokenizer: Any,
    record: VTDOTrainingRecord,
    *,
    profile: PrecisionProfile,
    common_label_positions: tuple[int, ...],
    differential_label_positions: tuple[int, ...],
) -> dict[str, Any]:
    import torch

    model.eval()
    if profile.gradient_checkpointing:
        _activate_deterministic_eval_checkpointing(model)
    model.zero_grad(set_to_none=True)
    batch, _ = _batch(tokenizer, record)
    labels = batch.pop("labels")
    prediction_positions, targets, supervised_tokens = _supervised_causal_projection(labels)
    all_label_positions = tuple(
        int(position) + 1 for position in prediction_positions.detach().cpu().tolist()
    )
    if (
        set(common_label_positions) & set(differential_label_positions)
        or tuple(sorted((*common_label_positions, *differential_label_positions)))
        != all_label_positions
    ):
        raise ValueError("precision calibration token regions do not partition support")
    ordinal_by_position = {
        position: ordinal for ordinal, position in enumerate(all_label_positions)
    }
    common_ordinals = torch.tensor(
        [ordinal_by_position[position] for position in common_label_positions],
        dtype=torch.long,
        device=targets.device,
    )
    differential_ordinals = torch.tensor(
        [ordinal_by_position[position] for position in differential_label_positions],
        dtype=torch.long,
        device=targets.device,
    )
    logits = _sparse_logits(
        model,
        batch,
        prediction_positions,
        projection_dtype=profile.sparse_projection_dtype,
    )
    losses = (
        _regional_loss(
            logits,
            targets,
            ordinals=None,
            accumulator_dtype=profile.loss_accumulator_dtype,
        ),
        _regional_loss(
            logits,
            targets,
            ordinals=common_ordinals,
            accumulator_dtype=profile.loss_accumulator_dtype,
        ),
        _regional_loss(
            logits,
            targets,
            ordinals=differential_ordinals,
            accumulator_dtype=profile.loss_accumulator_dtype,
        ),
    )
    counts = (
        supervised_tokens,
        len(common_label_positions),
        len(differential_label_positions),
    )
    gradients: list[dict[str, Any]] = []
    loss_values: list[float] = []
    for index, loss in enumerate(losses):
        if not torch.isfinite(loss):
            raise ValueError("precision calibration produced a non-finite loss")
        model.zero_grad(set_to_none=True)
        loss.backward(retain_graph=index < len(losses) - 1)
        gradients.append(_collect_trainable_gradients(model))
        loss_values.append(float(loss.detach().double().cpu()))
    full_gradient, common_gradient, differential_gradient = gradients
    common_count, differential_count = counts[1], counts[2]
    recomposed = _weighted_gradient(
        [common_gradient, differential_gradient],
        [float(common_count), float(differential_count)],
    )
    metrics = _token_gradient_decomposition_metrics(
        full_gradient,
        common_gradient,
        differential_gradient,
        common_token_count=common_count,
        differential_token_count=differential_count,
    )
    recomposed_loss = (
        common_count * loss_values[1] + differential_count * loss_values[2]
    ) / supervised_tokens
    del batch, labels, logits, losses, prediction_positions, targets
    return {
        "full_gradient": full_gradient,
        "recomposed_gradient": recomposed,
        "full_loss": loss_values[0],
        "common_loss": loss_values[1],
        "differential_loss": loss_values[2],
        "recomposed_loss": recomposed_loss,
        "loss_identity_absolute_error": abs(loss_values[0] - recomposed_loss),
        "supervised_tokens": supervised_tokens,
        "common_supervised_tokens": common_count,
        "differential_supervised_tokens": differential_count,
        **metrics,
    }


def _softmax_update(
    probabilities: dict[str, float],
    scores: dict[str, float],
) -> dict[str, float]:
    if set(probabilities) != set(scores) or not probabilities:
        raise ValueError("precision calibration update support differs")
    center = sum(probabilities[key] * scores[key] for key in probabilities)
    weights = {
        key: probabilities[key] * math.exp(scores[key] - center) for key in probabilities
    }
    normalizer = sum(weights.values())
    return {key: weights[key] / normalizer for key in sorted(weights)}


def _distribution_distance(
    left: dict[str, float],
    right: dict[str, float],
) -> tuple[float, float]:
    if set(left) != set(right) or not left:
        raise ValueError("precision calibration distributions differ in support")
    total_variation = 0.5 * sum(abs(left[key] - right[key]) for key in left)
    midpoint = {key: 0.5 * (left[key] + right[key]) for key in left}

    def kl(values: dict[str, float]) -> float:
        return sum(
            values[key] * math.log(values[key] / midpoint[key])
            for key in values
            if values[key] > 0
        )

    return total_variation, 0.5 * (kl(left) + kl(right))


def _rank_agreement(left: dict[str, float], right: dict[str, float]) -> float:
    if set(left) != set(right) or not left:
        raise ValueError("precision calibration ranks differ in support")
    left_order = tuple(sorted(left, key=lambda key: (-left[key], key)))
    right_order = tuple(sorted(right, key=lambda key: (-right[key], key)))
    return float(left_order == right_order)


def _summary(
    rows: list[dict[str, Any]],
    *,
    task_distributions: dict[str, Any],
    thresholds: dict[str, float] | None = None,
) -> dict[str, Any]:
    if not rows:
        raise ValueError("precision calibration has no result rows")
    by_task: dict[str, list[dict[str, Any]]] = {}
    for row in rows:
        by_task.setdefault(str(row["task_id"]), []).append(row)
    task_rows: list[dict[str, str | int | float]] = []
    for task_id, values in sorted(by_task.items()):
        probabilities = {
            str(key): float(value)
            for key, value in task_distributions[task_id]["probabilities"].items()
        }
        full_scores = {str(row["state_id"]): float(row["full_gp_score"]) for row in values}
        recomposed_scores = {
            str(row["state_id"]): float(row["recomposed_gp_score"]) for row in values
        }
        full_update = _softmax_update(probabilities, full_scores)
        recomposed_update = _softmax_update(probabilities, recomposed_scores)
        total_variation, jensen_shannon = _distribution_distance(
            full_update,
            recomposed_update,
        )
        task_rows.append(
            {
                "task_id": task_id,
                "state_count": len(values),
                "rank_agreement": _rank_agreement(full_scores, recomposed_scores),
                "update_total_variation": total_variation,
                "update_jensen_shannon": jensen_shannon,
            }
        )
    metrics = {
        "maximum_loss_identity_absolute_error": max(
            float(row["loss_identity_absolute_error"]) for row in rows
        ),
        "minimum_gradient_recomposition_cosine": min(
            float(row["token_gradient_recomposition_cosine"]) for row in rows
        ),
        "maximum_gradient_recomposition_relative_error": max(
            float(row["token_gradient_recomposition_relative_error"]) for row in rows
        ),
        "maximum_gp_score_absolute_delta": max(
            abs(float(row["full_gp_score"]) - float(row["recomposed_gp_score"]))
            for row in rows
        ),
        "minimum_task_rank_agreement": min(
            float(row["rank_agreement"]) for row in task_rows
        ),
        "maximum_update_total_variation": max(
            float(row["update_total_variation"]) for row in task_rows
        ),
        "maximum_update_jensen_shannon": max(
            float(row["update_jensen_shannon"]) for row in task_rows
        ),
    }
    applied_thresholds = thresholds or CALIBRATION_THRESHOLDS
    passed = all(
        (
            metrics[name] >= threshold
            if name.startswith("minimum_")
            else metrics[name] <= threshold
        )
        for name, threshold in applied_thresholds.items()
    )
    return {
        "metrics": metrics,
        "thresholds": applied_thresholds,
        "task_rows": task_rows,
        "status": "passed" if passed else "failed",
    }


def prepare(args: argparse.Namespace) -> None:
    source_dir = Path(args.source_run_dir).resolve()
    output_dir = Path(args.output_dir).resolve()
    source_plan_path = source_dir / "plan.json"
    source_manifest_path = source_dir / "evaluation_gradient_manifest.json"
    source_plan = _read_json(source_plan_path)
    source_manifest = _read_json(source_manifest_path)
    if source_plan.get("experiment_version") != SOURCE_GRADIENT_VERSION:
        raise ValueError("precision calibration requires the frozen v10 source run")
    if source_manifest.get("plan_hash") != source_plan.get("plan_hash"):
        raise ValueError("precision calibration source artifacts cross plans")
    if _sha256(Path(source_plan["target_records_path"])) != source_plan["target_records_sha256"]:
        raise ValueError("precision calibration source records changed")
    grouped: dict[str, list[dict[str, Any]]] = {}
    for job in source_plan["jobs"]:
        grouped.setdefault(str(job["task_id"]), []).append(job)
    if len(grouped) < 3:
        raise ValueError("precision calibration requires at least three complete tasks")
    task_ids = sorted(grouped)
    validation_task_ids = tuple(task_ids[-args.validation_task_count :])
    development_task_ids = tuple(
        task_id for task_id in task_ids if task_id not in set(validation_task_ids)
    )
    if not development_task_ids or not validation_task_ids:
        raise ValueError("precision calibration split is empty")
    split_jobs = {
        "development": tuple(
            job for task_id in development_task_ids for job in grouped[task_id]
        ),
        "validation": tuple(
            job for task_id in validation_task_ids for job in grouped[task_id]
        ),
    }
    plan: dict[str, Any] = {
        "calibration_version": CALIBRATION_VERSION,
        "source_gradient_version": SOURCE_GRADIENT_VERSION,
        "source_run_dir": str(source_dir),
        "source_plan_path": str(source_plan_path),
        "source_plan_sha256": _sha256(source_plan_path),
        "source_plan_hash": source_plan["plan_hash"],
        "source_evaluation_manifest_path": str(source_manifest_path),
        "source_evaluation_manifest_sha256": _sha256(source_manifest_path),
        "source_evaluation_manifest_hash": source_manifest["manifest_hash"],
        "model_dir": source_plan["model_dir"],
        "beneficiary_adapter_dir": source_plan["beneficiary_adapter_dir"],
        "beneficiary_adapter_tensor_sha256": source_plan[
            "beneficiary_adapter_tensor_sha256"
        ],
        "target_records_path": source_plan["target_records_path"],
        "target_records_sha256": source_plan["target_records_sha256"],
        "token_region_manifest_hash": source_plan["token_region_decomposition"][
            "manifest_hash"
        ],
        "token_regions": source_plan["token_region_decomposition"]["records"],
        "task_distributions": source_plan["task_distributions"],
        "development_task_ids": development_task_ids,
        "validation_task_ids": validation_task_ids,
        "split_jobs": split_jobs,
        "profiles": tuple(asdict(profile) for profile in PRECISION_PROFILES),
        "thresholds": CALIBRATION_THRESHOLDS,
        "development_safety_bounds": DEVELOPMENT_SAFETY_BOUNDS,
        "threshold_calibration_rule": THRESHOLD_CALIBRATION_RULE,
        "device_placement_policy": {
            "single_gpu": "explicit_cuda_device",
            "multi_gpu": "balanced_with_strict_whitelist",
            "maximum_weight_memory_per_selected_device_gib": SHARD_MEMORY_CAP_GIB,
            "nonselected_device_memory": 0,
            "allocator": "expandable_segments",
        },
        "selection_policy": (
            "development_safety_pass_then_min_update_tv_js_gp_delta_relative_error"
        ),
        "numeric_seed_policy": "source_job_gradient_seed_replayed_per_profile",
        "validation_blinding_policy": "validation_profile_run_only_after_selection_freeze",
        "production_effect": "none_until_independent_validation_passes",
    }
    plan["plan_hash"] = canonical_hash(plan, prefix="finance_gradient_precision_plan:")
    output_dir.mkdir(parents=True, exist_ok=True)
    _write_json(output_dir / "plan.json", plan)
    print(
        json.dumps(
            {
                "calibration_version": CALIBRATION_VERSION,
                "plan_hash": plan["plan_hash"],
                "development_task_ids": development_task_ids,
                "validation_task_ids": validation_task_ids,
                "development_job_count": len(split_jobs["development"]),
                "validation_job_count": len(split_jobs["validation"]),
                "profile_ids": tuple(profile.profile_id for profile in PRECISION_PROFILES),
                "thresholds": CALIBRATION_THRESHOLDS,
            },
            ensure_ascii=False,
            indent=2,
            sort_keys=True,
        )
    )


def _verify_plan(plan: dict[str, Any]) -> None:
    if plan.get("calibration_version") != CALIBRATION_VERSION:
        raise ValueError("precision calibration plan version differs")
    payload = dict(plan)
    expected = payload.pop("plan_hash", None)
    if canonical_hash(payload, prefix="finance_gradient_precision_plan:") != expected:
        raise ValueError("precision calibration plan identity failed replay")
    for path_key, hash_key in (
        ("source_plan_path", "source_plan_sha256"),
        ("source_evaluation_manifest_path", "source_evaluation_manifest_sha256"),
        ("target_records_path", "target_records_sha256"),
    ):
        if _sha256(Path(plan[path_key])) != plan[hash_key]:
            raise ValueError(f"precision calibration input changed:{path_key}")


def run_profile(args: argparse.Namespace) -> None:
    import torch

    output_dir = Path(args.output_dir).resolve()
    plan = _read_json(output_dir / "plan.json")
    _verify_plan(plan)
    split = str(args.split)
    if split not in SPLITS:
        raise ValueError("unknown precision calibration split")
    profile = _profile(args.profile_id)
    result_dir = output_dir / split
    result_path = result_dir / f"{profile.profile_id}.json"
    if result_path.exists():
        raise ValueError("precision calibration result already exists and is immutable")
    selection_path = output_dir / "selection.json"
    if split == "validation":
        if not selection_path.is_file():
            raise ValueError("validation cannot run before profile selection is frozen")
        selection = _read_json(selection_path)
        if selection.get("selected_profile_id") != profile.profile_id:
            raise ValueError("validation may run only for the frozen selected profile")
        summary_thresholds = {
            str(key): float(value)
            for key, value in selection["frozen_validation_thresholds"].items()
        }
    else:
        summary_thresholds = CALIBRATION_THRESHOLDS
    gpu_ids = tuple(int(value) for value in args.gpu_ids)
    if not gpu_ids or len(set(gpu_ids)) != len(gpu_ids):
        raise ValueError("precision calibration requires unique GPU ids")
    if any(gpu_id < 0 or gpu_id >= torch.cuda.device_count() for gpu_id in gpu_ids):
        raise ValueError("precision calibration GPU id is not visible")
    torch.cuda.set_device(gpu_ids[0])
    for gpu_id in gpu_ids:
        torch.cuda.reset_peak_memory_stats(gpu_id)
    _seed_everything(20260840)
    _configure_numeric_policy(profile)
    tokenizer = _load_tokenizer(Path(plan["model_dir"]))
    started = time.monotonic()
    result: dict[str, Any] = {
        "calibration_version": CALIBRATION_VERSION,
        "plan_hash": plan["plan_hash"],
        "split": split,
        "profile": asdict(profile),
        "requested_cuda_device_ids": gpu_ids,
        "cuda_visible_devices_env": os.environ.get("CUDA_VISIBLE_DEVICES"),
    }
    try:
        model, device_map = _load_calibration_model(
            model_dir=Path(plan["model_dir"]),
            adapter_dir=Path(plan["beneficiary_adapter_dir"]),
            profile=profile,
            gpu_ids=gpu_ids,
        )
        if _adapter_tensor_sha256(model) != plan["beneficiary_adapter_tensor_sha256"]:
            raise ValueError("precision calibration loaded another beneficiary Adapter")
        source_manifest = _read_json(Path(plan["source_evaluation_manifest_path"]))
        parameter_manifest, parameter_manifest_hash = _gradient_parameter_manifest(model)
        if parameter_manifest != source_manifest["parameter_manifest"]:
            raise ValueError("precision calibration parameter manifest differs from v10")
        if parameter_manifest_hash != source_manifest["parameter_manifest_hash"]:
            raise ValueError("precision calibration parameter identity differs from v10")
        _, objective_gradients = _load_gradient_artifacts(source_manifest)
        objective = objective_gradients["validation"]
        objective_norm = _gradient_norm(objective)
        records = _load_records(Path(plan["target_records_path"]))
        rows = []
        for job in plan["split_jobs"][split]:
            _seed_everything(int(job["gradient_seed"]))
            _configure_numeric_policy(profile)
            regions = plan["token_regions"][job["record_id"]]
            decomposition = _gradient_decomposition(
                model,
                tokenizer,
                records[job["record_id"]],
                profile=profile,
                common_label_positions=tuple(
                    int(value) for value in regions["common_label_positions"]
                ),
                differential_label_positions=tuple(
                    int(value) for value in regions["differential_label_positions"]
                ),
            )
            full = decomposition.pop("full_gradient")
            recomposed = decomposition.pop("recomposed_gradient")
            _, full_score, _, _ = _gradient_alignment(full, objective)
            _, recomposed_score, _, _ = _gradient_alignment(recomposed, objective)
            rows.append(
                {
                    "job_id": job["job_id"],
                    "task_id": job["task_id"],
                    "task_type": job["task_type"],
                    "state_id": job["state_id"],
                    "record_id": job["record_id"],
                    "full_gp_score": full_score,
                    "recomposed_gp_score": recomposed_score,
                    "objective_gradient_norm": objective_norm,
                    **decomposition,
                }
            )
            del full, recomposed
        result.update(
            {
                "status": "completed",
                "rows": rows,
                "summary": _summary(
                    rows,
                    task_distributions=plan["task_distributions"],
                    thresholds=summary_thresholds,
                ),
                "resolved_hf_device_map": device_map,
                "resolved_hf_device_map_hash": canonical_hash(
                    device_map,
                    prefix="finance_gradient_precision_device_map:",
                ),
                "trainable_parameter_manifest": parameter_manifest,
                "trainable_parameter_manifest_hash": parameter_manifest_hash,
                "trainable_parameter_dtypes": tuple(
                    sorted({str(value["dtype"]) for value in parameter_manifest.values()})
                ),
            }
        )
        del model, objective_gradients, objective
    except torch.cuda.OutOfMemoryError as error:
        result.update(
            {
                "status": "resource_failed",
                "error_type": type(error).__name__,
                "error": str(error),
            }
        )
    result.update(
        {
            "runtime_seconds": time.monotonic() - started,
            "peak_gpu_memory_bytes_by_requested_device": {
                str(gpu_id): int(torch.cuda.max_memory_allocated(gpu_id)) for gpu_id in gpu_ids
            },
            "torch_version": torch.__version__,
        }
    )
    result["result_hash"] = canonical_hash(result, prefix="finance_gradient_precision_result:")
    result_dir.mkdir(parents=True, exist_ok=True)
    _write_json(result_path, result)
    gc.collect()
    torch.cuda.empty_cache()
    if not bool(getattr(args, "quiet", False)):
        print(json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True))


def _matrix_worker(
    output_dir: str,
    profile_id: str,
    gpu_ids: tuple[int, ...],
) -> dict[str, Any]:
    result_path = Path(output_dir) / "development" / f"{profile_id}.json"
    resumed = result_path.is_file()
    if not resumed:
        run_profile(
            argparse.Namespace(
                output_dir=output_dir,
                profile_id=profile_id,
                split="development",
                gpu_ids=gpu_ids,
                quiet=True,
            )
        )
    result = _read_json(result_path)
    return {
        "profile_id": profile_id,
        "gpu_ids": gpu_ids,
        "status": result["status"],
        "summary_status": result.get("summary", {}).get("status"),
        "runtime_seconds": result["runtime_seconds"],
        "peak_gpu_memory_bytes_by_requested_device": result[
            "peak_gpu_memory_bytes_by_requested_device"
        ],
        "result_hash": result["result_hash"],
        "resumed": resumed,
    }


def _parse_assignment(value: str) -> tuple[str, tuple[int, ...]]:
    profile_id, separator, raw_gpu_ids = value.partition("=")
    if not separator or not profile_id or not raw_gpu_ids:
        raise ValueError("precision assignment must use profile_id=gpu_id[,gpu_id]")
    gpu_ids = tuple(int(item) for item in raw_gpu_ids.split(","))
    _profile(profile_id)
    if not gpu_ids or len(set(gpu_ids)) != len(gpu_ids):
        raise ValueError("precision assignment GPU ids must be unique")
    return profile_id, gpu_ids


def run_development_matrix(args: argparse.Namespace) -> None:
    output_dir = Path(args.output_dir).resolve()
    plan = _read_json(output_dir / "plan.json")
    _verify_plan(plan)
    assignments = tuple(_parse_assignment(value) for value in args.assignment)
    expected_profiles = {profile.profile_id for profile in PRECISION_PROFILES}
    observed_profiles = {profile_id for profile_id, _ in assignments}
    if observed_profiles != expected_profiles or len(assignments) != len(expected_profiles):
        raise ValueError("precision matrix must assign every profile exactly once")
    all_gpu_ids = tuple(gpu_id for _, gpu_ids in assignments for gpu_id in gpu_ids)
    if len(set(all_gpu_ids)) != len(all_gpu_ids):
        raise ValueError("precision matrix profile GPU whitelists overlap")
    os.environ.setdefault("PYTORCH_CUDA_ALLOC_CONF", "expandable_segments:True")
    context = multiprocessing.get_context("spawn")
    reports: list[dict[str, Any]] = []
    failures: list[dict[str, str]] = []
    with ProcessPoolExecutor(max_workers=len(assignments), mp_context=context) as executor:
        futures = {
            executor.submit(
                _matrix_worker,
                str(output_dir),
                profile_id,
                gpu_ids,
            ): profile_id
            for profile_id, gpu_ids in assignments
        }
        for future in as_completed(futures):
            profile_id = futures[future]
            try:
                reports.append(future.result())
            except Exception as error:
                failures.append(
                    {
                        "profile_id": profile_id,
                        "error_type": type(error).__name__,
                        "error": str(error),
                    }
                )
    summary: dict[str, Any] = {
        "calibration_version": CALIBRATION_VERSION,
        "plan_hash": plan["plan_hash"],
        "assignments": tuple(
            {"profile_id": profile_id, "gpu_ids": gpu_ids}
            for profile_id, gpu_ids in assignments
        ),
        "reports": tuple(sorted(reports, key=lambda row: str(row["profile_id"]))),
        "failures": tuple(sorted(failures, key=lambda row: row["profile_id"])),
        "status": "completed" if not failures else "failed",
    }
    summary["summary_hash"] = canonical_hash(
        summary,
        prefix="finance_gradient_precision_matrix:",
    )
    _write_json(output_dir / "development_matrix_summary.json", summary)
    print(json.dumps(summary, ensure_ascii=False, indent=2, sort_keys=True))
    if failures:
        raise RuntimeError("precision development matrix contains worker failures")


def freeze_selection(args: argparse.Namespace) -> None:
    output_dir = Path(args.output_dir).resolve()
    plan = _read_json(output_dir / "plan.json")
    _verify_plan(plan)
    validation_dir = output_dir / "validation"
    if validation_dir.exists() and any(validation_dir.glob("*.json")):
        raise ValueError("profile selection must be frozen before validation is observed")
    results = []
    for profile in PRECISION_PROFILES:
        path = output_dir / "development" / f"{profile.profile_id}.json"
        if not path.is_file():
            raise ValueError(f"missing development precision profile:{profile.profile_id}")
        result = _read_json(path)
        if result.get("plan_hash") != plan["plan_hash"]:
            raise ValueError("precision development result crosses plans")
        results.append(result)
    eligible = [
        result
        for result in results
        if result.get("status") == "completed"
        and _development_eligible(result.get("summary", {}).get("metrics", {}))
    ]
    selected = (
        min(
            eligible,
            key=lambda result: (
                float(
                    result["summary"]["metrics"]["maximum_update_total_variation"]
                ),
                float(
                    result["summary"]["metrics"]["maximum_update_jensen_shannon"]
                ),
                float(
                    result["summary"]["metrics"]["maximum_gp_score_absolute_delta"]
                ),
                float(
                    result["summary"]["metrics"]
                    ["maximum_gradient_recomposition_relative_error"]
                ),
                str(result["profile"]["profile_id"]),
            ),
        )
        if eligible
        else None
    )
    selection: dict[str, Any] = {
        "calibration_version": CALIBRATION_VERSION,
        "plan_hash": plan["plan_hash"],
        "status": "frozen" if selected is not None else "calibration_failed",
        "selected_profile_id": (
            str(selected["profile"]["profile_id"]) if selected is not None else None
        ),
        "development_result_hashes": tuple(
            str(result["result_hash"]) for result in results
        ),
        "eligible_profile_ids": tuple(
            str(result["profile"]["profile_id"]) for result in eligible
        ),
        "selection_policy": plan["selection_policy"],
        "development_safety_bounds": plan["development_safety_bounds"],
        "threshold_calibration_rule": plan["threshold_calibration_rule"],
        "frozen_validation_thresholds": (
            _derive_validation_thresholds(selected["summary"]["metrics"])
            if selected is not None
            else None
        ),
        "validation_observed": False,
    }
    selection["selection_hash"] = canonical_hash(
        selection,
        prefix="finance_gradient_precision_selection:",
    )
    _write_json(output_dir / "selection.json", selection)
    print(json.dumps(selection, ensure_ascii=False, indent=2, sort_keys=True))


def aggregate(args: argparse.Namespace) -> None:
    output_dir = Path(args.output_dir).resolve()
    plan = _read_json(output_dir / "plan.json")
    _verify_plan(plan)
    selection = _read_json(output_dir / "selection.json")
    profile_id = selection.get("selected_profile_id")
    if selection.get("status") != "frozen" or not isinstance(profile_id, str):
        raise ValueError("precision calibration has no frozen profile")
    development = _read_json(output_dir / "development" / f"{profile_id}.json")
    validation = _read_json(output_dir / "validation" / f"{profile_id}.json")
    validation_passed = bool(
        validation.get("status") == "completed"
        and validation.get("summary", {}).get("status") == "passed"
    )
    report: dict[str, Any] = {
        "calibration_version": CALIBRATION_VERSION,
        "plan_hash": plan["plan_hash"],
        "selection_hash": selection["selection_hash"],
        "selected_profile": development["profile"],
        "development_result_hash": development["result_hash"],
        "validation_result_hash": validation["result_hash"],
        "development_summary": development["summary"],
        "validation_summary": validation["summary"],
        "status": "passed" if validation_passed else "failed",
        "production_authorized": False,
        "authorization_effect": (
            "numeric_profile_frozen_for_independent_30_task_candidate_run"
            if validation_passed
            else "none"
        ),
        "claim_boundary": (
            "Numerical calibration does not authorize Contribution or VTDO energy updates."
        ),
    }
    report["report_hash"] = canonical_hash(
        report,
        prefix="finance_gradient_precision_report:",
    )
    _write_json(output_dir / "report.json", report)
    if validation_passed:
        contract = _build_numeric_contract(
            plan=plan,
            selection=selection,
            development=development,
            validation=validation,
        )
        _write_json(output_dir / "frozen_numeric_contract.json", contract)
    print(json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True))


def _build_numeric_contract(
    *,
    plan: dict[str, Any],
    selection: dict[str, Any],
    development: dict[str, Any],
    validation: dict[str, Any],
) -> dict[str, Any]:
    profile_id = selection.get("selected_profile_id")
    frozen_thresholds = selection.get("frozen_validation_thresholds")
    observed_thresholds = validation.get("summary", {}).get("thresholds")
    if selection.get("status") != "frozen" or not isinstance(profile_id, str):
        raise ValueError("precision calibration has no frozen profile")
    if not isinstance(frozen_thresholds, dict) or not frozen_thresholds:
        raise ValueError("precision calibration has no frozen validation thresholds")
    if observed_thresholds != frozen_thresholds:
        raise ValueError("validation did not replay the frozen threshold contract")
    if development.get("profile", {}).get("profile_id") != profile_id:
        raise ValueError("development result does not match selected precision profile")
    if validation.get("profile", {}).get("profile_id") != profile_id:
        raise ValueError("validation result does not match selected precision profile")

    contract: dict[str, Any] = {
        "calibration_version": CALIBRATION_VERSION,
        "plan_hash": plan["plan_hash"],
        "selection_hash": selection["selection_hash"],
        "selected_profile": development["profile"],
        "thresholds": frozen_thresholds,
        "development_result_hash": development["result_hash"],
        "validation_result_hash": validation["result_hash"],
        "allowed_next_run_role": "independent_30_task_production_candidate",
    }
    contract["contract_hash"] = canonical_hash(
        contract,
        prefix="finance_gradient_precision_contract:",
    )
    return contract


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Calibrate Gradient Projection numeric precision")
    subparsers = parser.add_subparsers(dest="command", required=True)
    prepare_parser = subparsers.add_parser("prepare")
    prepare_parser.add_argument("--source-run-dir", required=True)
    prepare_parser.add_argument("--output-dir", required=True)
    prepare_parser.add_argument("--validation-task-count", type=int, default=1)
    prepare_parser.set_defaults(handler=prepare)
    run_parser = subparsers.add_parser("run-profile")
    run_parser.add_argument("--output-dir", required=True)
    run_parser.add_argument("--profile-id", required=True)
    run_parser.add_argument("--split", choices=SPLITS, required=True)
    run_parser.add_argument("--gpu-ids", nargs="+", type=int, required=True)
    run_parser.set_defaults(handler=run_profile)
    matrix_parser = subparsers.add_parser("run-development-matrix")
    matrix_parser.add_argument("--output-dir", required=True)
    matrix_parser.add_argument("--assignment", action="append", required=True)
    matrix_parser.set_defaults(handler=run_development_matrix)
    selection_parser = subparsers.add_parser("freeze-selection")
    selection_parser.add_argument("--output-dir", required=True)
    selection_parser.set_defaults(handler=freeze_selection)
    aggregate_parser = subparsers.add_parser("aggregate")
    aggregate_parser.add_argument("--output-dir", required=True)
    aggregate_parser.set_defaults(handler=aggregate)
    return parser


def main() -> None:
    args = _parser().parse_args()
    args.handler(args)


if __name__ == "__main__":
    main()
