from __future__ import annotations

import argparse
import gc
import hashlib
import json
import math
import os
import random
import statistics
import time
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, Literal

from trusted_synthesis.experiments.vtdo_experiment.phase1_contribution_gradient import (
    GRADIENT_ALIGNMENT_VERSION,
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
from trusted_synthesis.experiments.vtdo_experiment.phase1_gradient_precision_calibration import (
    PrecisionProfile,
    _adapter_tensor_sha256,
    _batch,
    _configure_numeric_policy,
    _load_calibration_model,
    _load_records,
    _load_tokenizer,
    _seed_everything,
    _shared_token_region_losses,
    _sparse_logits,
)
from trusted_synthesis.experiments.vtdo_experiment.phase1_gradient_precision_calibration_v5 import (
    GIB,
    POPULATION_VERSION,
    _combined_summary,
    _read_json,
    _replay_hash,
    _sha256,
    _source_descriptor,
    _write_json,
)
from trusted_synthesis.hashing import canonical_hash

ROOT_CAUSE_VERSION = "finance_gradient_numeric_root_cause.v3"
CHECKPOINT_VERSION = "finance_gradient_numeric_root_cause_checkpoint.v3"
SAVED_TENSOR_POLICY = "stride_preserving_pinned_cpu_roundtrip_synchronous_restore"
SAVED_TENSOR_RESTORE_NON_BLOCKING = False
DIAGNOSTIC_JOB_SAMPLING_POLICY = "one_lowest_realization_index_per_task_state"
MODEL_INPUT_DEVICE_POLICY = "input_embedding_weight_device"
SDPA_BACKEND_POLICY = "torch_efficient_attention_for_all_cuda_profiles"
GQA_EXECUTION_POLICY = "explicit_repeat_kv_before_fused_sdpa"
SPLITS = ("development", "validation")
VJPMode = Literal[
    "shared_retained_backward",
    "separate_forward_backward",
    "functional_call_autograd",
]
ProjectionExecutionDType = Literal["model", "float32", "bfloat16"]
FIXED_NUMERIC_THRESHOLDS = {
    "maximum_loss_identity_absolute_error": 1e-6,
    "minimum_gradient_recomposition_cosine": 0.99967,
    "maximum_gradient_recomposition_relative_error": 0.027,
    "maximum_gp_score_absolute_delta": 0.0023,
    "maximum_update_total_variation": 0.00023,
    "maximum_update_jensen_shannon": 1e-6,
}
NUMERIC_THRESHOLD_KEYS = frozenset(FIXED_NUMERIC_THRESHOLDS)
IMPLEMENTATION_DEPENDENCY_FILENAMES = (
    "phase1_gradient_numeric_root_cause.py",
    "phase1_contribution_gradient.py",
    "phase1_gradient_precision_calibration.py",
    "phase1_gradient_precision_calibration_v5.py",
)


def _implementation_manifest() -> dict[str, str]:
    module_dir = Path(__file__).resolve().parent
    return {
        filename: _sha256(module_dir / filename) for filename in IMPLEMENTATION_DEPENDENCY_FILENAMES
    }


@dataclass(frozen=True)
class RootCauseProfile:
    profile_id: str
    precision: PrecisionProfile
    vjp_mode: VJPMode
    factor_id: str
    baseline_profile_id: str | None
    intervention_count: int
    required_gpu_count: int
    projection_execution_dtype: ProjectionExecutionDType = "model"

    @property
    def algorithm_contract(self) -> dict[str, Any]:
        fresh_forward = self.vjp_mode in {
            "separate_forward_backward",
            "functional_call_autograd",
        }
        return {
            "root_cause_version": ROOT_CAUSE_VERSION,
            "vjp_mode": self.vjp_mode,
            "forward_graph_count_per_realization": (3 if fresh_forward else 1),
            "cross_entropy_evaluation_count_per_realization": (3 if fresh_forward else 1),
            "region_loss_policy": (
                "slice_one_shared_per_token_cross_entropy_vector"
                if not fresh_forward
                else "fresh_forward_and_cross_entropy_per_region"
            ),
            "gradient_extraction": (
                "torch_autograd_grad"
                if self.vjp_mode == "functional_call_autograd"
                else "tensor_backward"
            ),
            "functional_decoder_call": self.vjp_mode == "functional_call_autograd",
            "saved_tensor_policy": SAVED_TENSOR_POLICY,
            "saved_tensor_restore_non_blocking": SAVED_TENSOR_RESTORE_NON_BLOCKING,
            "model_input_device_policy": MODEL_INPUT_DEVICE_POLICY,
            "sdpa_backend_policy": SDPA_BACKEND_POLICY,
            "gqa_execution_policy": GQA_EXECUTION_POLICY,
            "projection_execution_dtype": self.projection_execution_dtype,
            "effective_projection_dtype": (
                self.precision.model_dtype
                if self.projection_execution_dtype == "model"
                else self.projection_execution_dtype
            ),
            "precision": asdict(self.precision),
        }


def _precision(
    profile_id: str,
    *,
    model_dtype: Literal["bfloat16", "float32"] = "bfloat16",
    sparse_projection_dtype: Literal["model", "float32"] = "model",
    loss_accumulator_dtype: Literal["float32", "float64"] = "float32",
    gradient_checkpointing: bool = True,
    cuda_matmul_allow_tf32: bool = True,
    float32_matmul_precision: Literal["highest", "high"] = "high",
) -> PrecisionProfile:
    return PrecisionProfile(
        profile_id=profile_id,
        model_dtype=model_dtype,
        sparse_projection_dtype=sparse_projection_dtype,
        loss_accumulator_dtype=loss_accumulator_dtype,
        gradient_checkpointing=gradient_checkpointing,
        cuda_matmul_allow_tf32=cuda_matmul_allow_tf32,
        float32_matmul_precision=float32_matmul_precision,
    )


ROOT_CAUSE_PROFILES = (
    RootCauseProfile(
        profile_id="control_bf16_checkpoint_tf32",
        precision=_precision("control_bf16_checkpoint_tf32"),
        vjp_mode="shared_retained_backward",
        factor_id="control",
        baseline_profile_id=None,
        intervention_count=0,
        required_gpu_count=1,
    ),
    RootCauseProfile(
        profile_id="projection_fp32_only",
        precision=_precision(
            "projection_fp32_only",
            sparse_projection_dtype="float32",
        ),
        vjp_mode="shared_retained_backward",
        factor_id="sparse_projection_dtype",
        baseline_profile_id="control_bf16_checkpoint_tf32",
        intervention_count=1,
        required_gpu_count=1,
        projection_execution_dtype="float32",
    ),
    RootCauseProfile(
        profile_id="accumulation_fp64_only",
        precision=_precision(
            "accumulation_fp64_only",
            loss_accumulator_dtype="float64",
        ),
        vjp_mode="shared_retained_backward",
        factor_id="loss_accumulation_dtype",
        baseline_profile_id="control_bf16_checkpoint_tf32",
        intervention_count=1,
        required_gpu_count=1,
    ),
    RootCauseProfile(
        profile_id="tf32_off_only",
        precision=_precision(
            "tf32_off_only",
            cuda_matmul_allow_tf32=False,
            float32_matmul_precision="highest",
        ),
        vjp_mode="shared_retained_backward",
        factor_id="tf32_policy",
        baseline_profile_id="control_bf16_checkpoint_tf32",
        intervention_count=1,
        required_gpu_count=1,
    ),
    RootCauseProfile(
        profile_id="checkpoint_on_separate_forward",
        precision=_precision(
            "checkpoint_on_separate_forward",
        ),
        vjp_mode="separate_forward_backward",
        factor_id="vjp_separate_forward",
        baseline_profile_id="control_bf16_checkpoint_tf32",
        intervention_count=1,
        required_gpu_count=1,
    ),
    RootCauseProfile(
        profile_id="checkpoint_off_separate_forward",
        precision=_precision(
            "checkpoint_off_separate_forward",
            gradient_checkpointing=False,
        ),
        vjp_mode="separate_forward_backward",
        factor_id="activation_checkpointing",
        baseline_profile_id="checkpoint_on_separate_forward",
        intervention_count=2,
        required_gpu_count=3,
    ),
    RootCauseProfile(
        profile_id="checkpoint_off_functional_call",
        precision=_precision(
            "checkpoint_off_functional_call",
            gradient_checkpointing=False,
        ),
        vjp_mode="functional_call_autograd",
        factor_id="vjp_functional_call",
        baseline_profile_id="checkpoint_off_separate_forward",
        intervention_count=2,
        required_gpu_count=3,
    ),
    RootCauseProfile(
        profile_id="fp32_activation_strict",
        precision=_precision(
            "fp32_activation_strict",
            model_dtype="float32",
            cuda_matmul_allow_tf32=False,
            float32_matmul_precision="highest",
        ),
        vjp_mode="shared_retained_backward",
        factor_id="activation_dtype",
        baseline_profile_id="tf32_off_only",
        intervention_count=2,
        required_gpu_count=3,
        projection_execution_dtype="bfloat16",
    ),
)
PROFILE_BY_ID = {profile.profile_id: profile for profile in ROOT_CAUSE_PROFILES}
if len(PROFILE_BY_ID) != len(ROOT_CAUSE_PROFILES):
    raise RuntimeError("numeric root-cause profile ids are duplicated")

PROFILE_RESOURCE_CONTRACTS = {
    profile.profile_id: {
        "required_gpu_count": profile.required_gpu_count,
        "minimum_free_memory_bytes_per_gpu": 64 * GIB,
    }
    for profile in ROOT_CAUSE_PROFILES
}
PROFILE_FACTOR_CHANGES = {
    "projection_fp32_only": ("effective_projection_dtype",),
    "accumulation_fp64_only": ("loss_accumulator_dtype",),
    "tf32_off_only": ("cuda_matmul_allow_tf32", "float32_matmul_precision"),
    "checkpoint_on_separate_forward": ("vjp_mode",),
    "checkpoint_off_separate_forward": ("gradient_checkpointing",),
    "checkpoint_off_functional_call": ("vjp_mode",),
    "fp32_activation_strict": ("model_dtype",),
}


def _serialized_factor_changes() -> dict[str, list[str]]:
    """Return the JSON-native representation frozen into experiment plans."""

    return {profile_id: list(fields) for profile_id, fields in PROFILE_FACTOR_CHANGES.items()}


def _diagnostic_jobs(jobs: tuple[dict[str, Any], ...]) -> tuple[dict[str, Any], ...]:
    if not jobs:
        raise ValueError("numeric root-cause source contains no jobs")
    grouped: dict[tuple[str, str], list[dict[str, Any]]] = {}
    job_ids: set[str] = set()
    for job in jobs:
        task_id = str(job.get("task_id", ""))
        state_id = str(job.get("state_id", ""))
        job_id = str(job.get("job_id", ""))
        realization_index = job.get("realization_index")
        if not task_id or not state_id or not job_id or not isinstance(realization_index, int):
            raise ValueError("numeric root-cause diagnostic job identity is invalid")
        if realization_index < 0 or job_id in job_ids:
            raise ValueError("numeric root-cause diagnostic job identity is duplicated")
        job_ids.add(job_id)
        grouped.setdefault((task_id, state_id), []).append(job)
    selected = [
        min(values, key=lambda row: (int(row["realization_index"]), str(row["job_id"])))
        for values in grouped.values()
    ]
    return tuple(
        sorted(
            selected,
            key=lambda row: (str(row["task_id"]), str(row["state_id"]), str(row["job_id"])),
        )
    )


def _diagnostic_source_descriptor(source: dict[str, Any]) -> dict[str, Any]:
    full_jobs = tuple(source.get("jobs", ()))
    selected = _diagnostic_jobs(full_jobs)
    value = dict(source)
    value.update(
        {
            "full_job_count": len(full_jobs),
            "diagnostic_job_count": len(selected),
            "diagnostic_state_count": len(
                {(str(job["task_id"]), str(job["state_id"])) for job in selected}
            ),
            "diagnostic_job_sampling_policy": DIAGNOSTIC_JOB_SAMPLING_POLICY,
            "diagnostic_job_set_hash": canonical_hash(
                tuple(str(job["job_id"]) for job in selected),
                prefix="finance_gradient_numeric_root_cause_job_set:",
            ),
            "jobs": selected,
        }
    )
    return value


def _verify_diagnostic_source(source: dict[str, Any]) -> None:
    source_plan = _read_json(Path(source["plan_path"]))
    full_jobs = tuple(source_plan.get("jobs", ()))
    expected = _diagnostic_jobs(full_jobs)
    if tuple(source.get("jobs", ())) != expected:
        raise ValueError("numeric root-cause diagnostic job subset differs")
    if source.get("full_job_count") != len(full_jobs):
        raise ValueError("numeric root-cause full job count differs")
    if source.get("diagnostic_job_count") != len(expected):
        raise ValueError("numeric root-cause diagnostic job count differs")
    if source.get("diagnostic_state_count") != len(expected):
        raise ValueError("numeric root-cause diagnostic state count differs")
    if source.get("diagnostic_job_sampling_policy") != DIAGNOSTIC_JOB_SAMPLING_POLICY:
        raise ValueError("numeric root-cause diagnostic sampling policy differs")
    expected_hash = canonical_hash(
        tuple(str(job["job_id"]) for job in expected),
        prefix="finance_gradient_numeric_root_cause_job_set:",
    )
    if source.get("diagnostic_job_set_hash") != expected_hash:
        raise ValueError("numeric root-cause diagnostic job set hash differs")


def _factor_vector(profile: RootCauseProfile) -> dict[str, Any]:
    precision = profile.precision
    return {
        "model_dtype": precision.model_dtype,
        "effective_projection_dtype": (
            precision.model_dtype
            if profile.projection_execution_dtype == "model"
            else profile.projection_execution_dtype
        ),
        "loss_accumulator_dtype": precision.loss_accumulator_dtype,
        "gradient_checkpointing": precision.gradient_checkpointing,
        "cuda_matmul_allow_tf32": precision.cuda_matmul_allow_tf32,
        "float32_matmul_precision": precision.float32_matmul_precision,
        "vjp_mode": profile.vjp_mode,
    }


def _factor_differences(
    baseline: RootCauseProfile,
    variant: RootCauseProfile,
) -> tuple[str, ...]:
    left = _factor_vector(baseline)
    right = _factor_vector(variant)
    return tuple(sorted(key for key in left if left[key] != right[key]))


for _registered_profile in ROOT_CAUSE_PROFILES:
    _baseline_id = _registered_profile.baseline_profile_id
    if _baseline_id is None:
        continue
    _registered_changes = _factor_differences(
        PROFILE_BY_ID[_baseline_id],
        _registered_profile,
    )
    if _registered_changes != tuple(sorted(PROFILE_FACTOR_CHANGES[_registered_profile.profile_id])):
        raise RuntimeError(
            f"numeric root-cause factor contract differs:{_registered_profile.profile_id}"
        )

PROFILE_MANIFEST_HASH = canonical_hash(
    {
        "profiles": tuple(asdict(profile) for profile in ROOT_CAUSE_PROFILES),
        "factor_changes": PROFILE_FACTOR_CHANGES,
    },
    prefix="finance_gradient_numeric_root_cause_profiles:",
)
SELECTION_POLICY = (
    "fixed_v16_threshold_pass_then_min_max_relative_error_then_min_max_gp_delta_"
    "then_max_min_cosine_then_min_intervention_count"
)


def _profile(profile_id: str) -> RootCauseProfile:
    try:
        return PROFILE_BY_ID[profile_id]
    except KeyError as error:
        raise ValueError(f"unknown numeric root-cause profile:{profile_id}") from error


def _trainable_parameters(model: Any) -> tuple[tuple[str, Any], ...]:
    values = tuple(
        (name, parameter)
        for name, parameter in sorted(model.named_parameters())
        if parameter.requires_grad
    )
    if not values:
        raise ValueError("numeric root-cause model has no trainable parameters")
    return values


def _autograd_gradients(
    model: Any,
    loss: Any,
    *,
    retain_graph: bool,
) -> dict[str, Any]:
    import torch

    values = _trainable_parameters(model)
    gradients = torch.autograd.grad(
        loss,
        tuple(parameter for _, parameter in values),
        retain_graph=retain_graph,
        allow_unused=False,
    )
    output: dict[str, Any] = {}
    for (name, _), gradient in zip(values, gradients, strict=True):
        value = gradient.detach().float().cpu().contiguous()
        if not torch.isfinite(value).all():
            raise ValueError(f"numeric root-cause produced a non-finite gradient:{name}")
        output[name] = value
    return output


def _root_sparse_logits(
    model: Any,
    batch: dict[str, Any],
    prediction_positions: Any,
    *,
    projection_dtype: ProjectionExecutionDType,
) -> Any:
    if projection_dtype in {"model", "float32"}:
        return _sparse_logits(
            model,
            batch,
            prediction_positions,
            projection_dtype=projection_dtype,
        )
    import torch

    causal_model = model.get_base_model() if hasattr(model, "get_base_model") else model
    if not hasattr(causal_model, "get_decoder"):
        raise ValueError("numeric root-cause model does not expose a causal decoder")
    decoder_output = causal_model.get_decoder()(**batch, use_cache=False)
    hidden = decoder_output.last_hidden_state
    selected = hidden.index_select(1, prediction_positions.to(hidden.device))
    output_embedding = causal_model.get_output_embeddings()
    if output_embedding is None:
        raise ValueError("numeric root-cause model has no output embedding")
    selected = selected.to(output_embedding.weight.device)
    bias = getattr(output_embedding, "bias", None)
    return torch.nn.functional.linear(
        selected.bfloat16(),
        output_embedding.weight.bfloat16(),
        None if bias is None else bias.bfloat16(),
    )


def _functional_sparse_logits(
    model: Any,
    batch: dict[str, Any],
    prediction_positions: Any,
    *,
    projection_dtype: ProjectionExecutionDType,
) -> Any:
    import torch

    causal_model = model.get_base_model() if hasattr(model, "get_base_model") else model
    if not hasattr(causal_model, "get_decoder"):
        raise ValueError("numeric root-cause model does not expose a causal decoder")
    decoder = causal_model.get_decoder()
    parameters = dict(decoder.named_parameters())
    buffers = dict(decoder.named_buffers())
    decoder_output = torch.func.functional_call(
        decoder,
        (parameters, buffers),
        args=(),
        kwargs={**batch, "use_cache": False},
        tie_weights=True,
        strict=True,
    )
    hidden = decoder_output.last_hidden_state
    selected = hidden.index_select(1, prediction_positions.to(hidden.device))
    output_embedding = causal_model.get_output_embeddings()
    if output_embedding is None:
        raise ValueError("numeric root-cause model has no output embedding")
    selected = selected.to(output_embedding.weight.device)
    if projection_dtype == "model":
        return output_embedding(selected)
    bias = getattr(output_embedding, "bias", None)
    dtype = torch.float32 if projection_dtype == "float32" else torch.bfloat16
    return torch.nn.functional.linear(
        selected.to(dtype),
        output_embedding.weight.to(dtype),
        None if bias is None else bias.to(dtype),
    )


def _model_input_device(model: Any) -> Any:
    causal_model = model.get_base_model() if hasattr(model, "get_base_model") else model
    if not hasattr(causal_model, "get_input_embeddings"):
        raise ValueError("numeric root-cause model does not expose input embeddings")
    embedding = causal_model.get_input_embeddings()
    weight = getattr(embedding, "weight", None)
    if weight is None or not hasattr(weight, "device"):
        raise ValueError("numeric root-cause input embedding has no device")
    return weight.device


def _place_batch_on_model_input_device(
    model: Any,
    batch: dict[str, Any],
) -> dict[str, Any]:
    device = _model_input_device(model)
    return {name: value.to(device) for name, value in batch.items()}


def _explicit_kv_repeat_required(*_: Any, **__: Any) -> bool:
    return False


def _configure_attention_execution_policy(sdpa_module: Any | None = None) -> None:
    target_module = sdpa_module
    if target_module is None:
        import transformers.integrations.sdpa_attention as transformers_sdpa_module

        target_module = transformers_sdpa_module
    target_module.use_gqa_in_sdpa = _explicit_kv_repeat_required


def _losses_for_record(
    model: Any,
    tokenizer: Any,
    record: Any,
    *,
    profile: RootCauseProfile,
    common_label_positions: tuple[int, ...],
    differential_label_positions: tuple[int, ...],
    functional: bool,
) -> tuple[tuple[Any, Any, Any], tuple[int, int, int]]:
    import torch

    batch, _ = _batch(tokenizer, record)
    batch = _place_batch_on_model_input_device(model, batch)
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
        raise ValueError("numeric root-cause token regions do not partition support")
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
    logits = (
        _functional_sparse_logits(
            model,
            batch,
            prediction_positions,
            projection_dtype=profile.projection_execution_dtype,
        )
        if functional
        else _root_sparse_logits(
            model,
            batch,
            prediction_positions,
            projection_dtype=profile.projection_execution_dtype,
        )
    )
    losses = _shared_token_region_losses(
        logits,
        targets,
        common_ordinals=common_ordinals,
        differential_ordinals=differential_ordinals,
        accumulator_dtype=profile.precision.loss_accumulator_dtype,
    )
    return losses, (
        supervised_tokens,
        len(common_label_positions),
        len(differential_label_positions),
    )


def _root_cause_decomposition_impl(
    model: Any,
    tokenizer: Any,
    record: Any,
    *,
    profile: RootCauseProfile,
    common_label_positions: tuple[int, ...],
    differential_label_positions: tuple[int, ...],
) -> dict[str, Any]:
    import torch

    model.eval()
    if profile.precision.gradient_checkpointing:
        _activate_deterministic_eval_checkpointing(model)
    model.zero_grad(set_to_none=True)
    gradients: list[dict[str, Any]] = []
    loss_values: list[float] = []
    counts: tuple[int, int, int] | None = None

    if profile.vjp_mode in {
        "separate_forward_backward",
        "functional_call_autograd",
    }:
        for region_index in range(3):
            model.zero_grad(set_to_none=True)
            losses, current_counts = _losses_for_record(
                model,
                tokenizer,
                record,
                profile=profile,
                common_label_positions=common_label_positions,
                differential_label_positions=differential_label_positions,
                functional=profile.vjp_mode == "functional_call_autograd",
            )
            counts = current_counts if counts is None else counts
            if counts != current_counts:
                raise ValueError("numeric root-cause separate forwards changed token support")
            loss = losses[region_index]
            if not torch.isfinite(loss):
                raise ValueError("numeric root-cause produced a non-finite loss")
            if profile.vjp_mode == "functional_call_autograd":
                gradients.append(
                    _autograd_gradients(
                        model,
                        loss,
                        retain_graph=False,
                    )
                )
            else:
                loss.backward()
                gradients.append(_collect_trainable_gradients(model))
            loss_values.append(float(loss.detach().double().cpu()))
            del losses, loss
    else:
        losses, counts = _losses_for_record(
            model,
            tokenizer,
            record,
            profile=profile,
            common_label_positions=common_label_positions,
            differential_label_positions=differential_label_positions,
            functional=profile.vjp_mode == "functional_call_autograd",
        )
        for index, loss in enumerate(losses):
            if not torch.isfinite(loss):
                raise ValueError("numeric root-cause produced a non-finite loss")
            if profile.vjp_mode == "functional_call_autograd":
                gradients.append(
                    _autograd_gradients(
                        model,
                        loss,
                        retain_graph=index < len(losses) - 1,
                    )
                )
            else:
                model.zero_grad(set_to_none=True)
                loss.backward(retain_graph=index < len(losses) - 1)
                gradients.append(_collect_trainable_gradients(model))
            loss_values.append(float(loss.detach().double().cpu()))

    if counts is None:
        raise ValueError("numeric root-cause produced no token counts")
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
    recomposed_loss = (common_count * loss_values[1] + differential_count * loss_values[2]) / (
        common_count + differential_count
    )
    return {
        "full_gradient": full_gradient,
        "recomposed_gradient": recomposed,
        "full_loss": loss_values[0],
        "common_loss": loss_values[1],
        "differential_loss": loss_values[2],
        "recomposed_loss": recomposed_loss,
        "loss_identity_absolute_error": abs(loss_values[0] - recomposed_loss),
        "supervised_tokens": counts[0],
        "common_supervised_tokens": common_count,
        "differential_supervised_tokens": differential_count,
        **metrics,
    }


def _pack_saved_tensor_to_cpu(torch_module: Any, tensor: Any) -> tuple[Any, Any]:
    pin_memory = (
        torch_module.cuda.is_available() and tensor.device.type == "cuda" and not tensor.is_sparse
    )
    if tensor.layout == torch_module.strided:
        packed = torch_module.empty_strided(
            tensor.size(),
            tensor.stride(),
            dtype=tensor.dtype,
            pin_memory=pin_memory,
        )
    else:
        packed = torch_module.empty(
            tensor.size(),
            dtype=tensor.dtype,
            layout=tensor.layout,
            pin_memory=False,
        )
    packed.copy_(tensor)
    return tensor.device, packed


def _unpack_saved_tensor_from_cpu(packed: tuple[Any, Any]) -> Any:
    device, tensor = packed
    return tensor.to(device, non_blocking=SAVED_TENSOR_RESTORE_NON_BLOCKING)


def _stride_preserving_saved_tensors(torch_module: Any) -> Any:
    return torch_module.autograd.graph.saved_tensors_hooks(
        lambda tensor: _pack_saved_tensor_to_cpu(torch_module, tensor),
        _unpack_saved_tensor_from_cpu,
    )


def _root_cause_decomposition(
    model: Any,
    tokenizer: Any,
    record: Any,
    *,
    profile: RootCauseProfile,
    common_label_positions: tuple[int, ...],
    differential_label_positions: tuple[int, ...],
) -> dict[str, Any]:
    import torch

    parameter_iterator = getattr(model, "parameters", None)
    parameters = tuple(parameter_iterator()) if callable(parameter_iterator) else ()
    uses_cuda = any(parameter.device.type == "cuda" for parameter in parameters)
    if not uses_cuda:
        return _root_cause_decomposition_impl(
            model,
            tokenizer,
            record,
            profile=profile,
            common_label_positions=common_label_positions,
            differential_label_positions=differential_label_positions,
        )
    from torch.nn.attention import SDPBackend, sdpa_kernel

    _configure_attention_execution_policy()
    with (
        _stride_preserving_saved_tensors(torch),
        sdpa_kernel(SDPBackend.EFFICIENT_ATTENTION),
    ):
        return _root_cause_decomposition_impl(
            model,
            tokenizer,
            record,
            profile=profile,
            common_label_positions=common_label_positions,
            differential_label_positions=differential_label_positions,
        )


def _checkpoint_path(
    output_dir: Path,
    *,
    split: str,
    profile_id: str,
    job_id: str,
) -> Path:
    digest = hashlib.sha256(job_id.encode("utf-8")).hexdigest()
    return output_dir / "checkpoints" / split / profile_id / f"{digest}.json"


def _checkpoint_source_identity(source: dict[str, Any]) -> dict[str, Any]:
    keys = (
        "plan_hash",
        "plan_sha256",
        "manifest_hash",
        "manifest_sha256",
        "objective_split",
        "objective_record_set_id",
        "target_records_sha256",
        "token_region_manifest_hash",
        "beneficiary_adapter_tensor_sha256",
    )
    return {key: source[key] for key in keys}


def _build_checkpoint(
    *,
    plan: dict[str, Any],
    source: dict[str, Any],
    split: str,
    profile: RootCauseProfile,
    job: dict[str, Any],
    row: dict[str, Any],
) -> dict[str, Any]:
    value: dict[str, Any] = {
        "checkpoint_version": CHECKPOINT_VERSION,
        "root_cause_version": ROOT_CAUSE_VERSION,
        "plan_hash": plan["plan_hash"],
        "split": split,
        "profile": asdict(profile),
        "profile_algorithm_contract": profile.algorithm_contract,
        "source_identity": _checkpoint_source_identity(source),
        "job": job,
        "row": row,
    }
    value["checkpoint_hash"] = canonical_hash(
        value,
        prefix="finance_gradient_numeric_root_cause_checkpoint:",
    )
    return value


def _verify_checkpoint(
    checkpoint: dict[str, Any],
    *,
    plan: dict[str, Any],
    source: dict[str, Any],
    split: str,
    profile: RootCauseProfile,
    job: dict[str, Any],
) -> None:
    _replay_hash(
        checkpoint,
        field="checkpoint_hash",
        prefix="finance_gradient_numeric_root_cause_checkpoint:",
    )
    expected = {
        "checkpoint_version": CHECKPOINT_VERSION,
        "root_cause_version": ROOT_CAUSE_VERSION,
        "plan_hash": plan["plan_hash"],
        "split": split,
        "profile": asdict(profile),
        "profile_algorithm_contract": profile.algorithm_contract,
        "source_identity": _checkpoint_source_identity(source),
        "job": job,
    }
    if any(checkpoint.get(key) != value for key, value in expected.items()):
        raise ValueError("numeric root-cause checkpoint identity differs")
    row = checkpoint.get("row")
    if not isinstance(row, dict):
        raise ValueError("numeric root-cause checkpoint row is invalid")
    for key in ("job_id", "task_id", "task_type", "state_id", "record_id", "gradient_seed"):
        if row.get(key) != job.get(key):
            raise ValueError("numeric root-cause checkpoint row identity differs")


def _load_checkpoints(
    output_dir: Path,
    *,
    plan: dict[str, Any],
    source: dict[str, Any],
    split: str,
    profile: RootCauseProfile,
) -> dict[str, dict[str, Any]]:
    jobs = {str(job["job_id"]): job for job in source["jobs"]}
    checkpoint_dir = output_dir / "checkpoints" / split / profile.profile_id
    if not checkpoint_dir.is_dir():
        return {}
    values: dict[str, dict[str, Any]] = {}
    for path in sorted(checkpoint_dir.glob("*.json")):
        checkpoint = _read_json(path)
        job_value = checkpoint.get("job")
        if not isinstance(job_value, dict):
            raise ValueError("numeric root-cause checkpoint job is invalid")
        job_id = str(job_value.get("job_id", ""))
        job = jobs.get(job_id)
        if job is None:
            raise ValueError("numeric root-cause checkpoint references an unknown job")
        if path != _checkpoint_path(
            output_dir,
            split=split,
            profile_id=profile.profile_id,
            job_id=job_id,
        ):
            raise ValueError("numeric root-cause checkpoint path identity differs")
        if job_id in values:
            raise ValueError("numeric root-cause checkpoint job is duplicated")
        _verify_checkpoint(
            checkpoint,
            plan=plan,
            source=source,
            split=split,
            profile=profile,
            job=job,
        )
        values[job_id] = checkpoint
    return values


def _verify_profile_registry(plan: dict[str, Any]) -> None:
    if tuple(plan.get("profiles", ())) != tuple(asdict(value) for value in ROOT_CAUSE_PROFILES):
        raise ValueError("numeric root-cause profile registry differs")
    if plan.get("profile_manifest_hash") != PROFILE_MANIFEST_HASH:
        raise ValueError("numeric root-cause profile manifest differs")
    if plan.get("profile_factor_changes") != _serialized_factor_changes():
        raise ValueError("numeric root-cause factor contracts differ")
    if plan.get("profile_resource_contracts") != PROFILE_RESOURCE_CONTRACTS:
        raise ValueError("numeric root-cause resource contracts differ")
    if plan.get("fixed_numeric_thresholds") != FIXED_NUMERIC_THRESHOLDS:
        raise ValueError("numeric root-cause fixed thresholds differ")
    if plan.get("selection_policy") != SELECTION_POLICY:
        raise ValueError("numeric root-cause selection policy differs")


def _verify_plan(plan: dict[str, Any]) -> None:
    if plan.get("root_cause_version") != ROOT_CAUSE_VERSION:
        raise ValueError("numeric root-cause plan version differs")
    _verify_profile_registry(plan)
    if _sha256(Path(__file__).resolve()) != plan.get("implementation_sha256"):
        raise ValueError("numeric root-cause implementation changed")
    implementation_manifest = _implementation_manifest()
    if plan.get("implementation_manifest") != implementation_manifest:
        raise ValueError("numeric root-cause dependency implementation changed")
    if plan.get("implementation_manifest_hash") != canonical_hash(
        implementation_manifest,
        prefix="finance_gradient_numeric_root_cause_implementation:",
    ):
        raise ValueError("numeric root-cause dependency manifest hash differs")
    _replay_hash(
        plan,
        field="plan_hash",
        prefix="finance_gradient_numeric_root_cause_plan:",
    )
    if _sha256(Path(plan["population_report_path"])) != plan["population_report_sha256"]:
        raise ValueError("numeric root-cause population report changed")
    for source in plan["sources"].values():
        for path_key, hash_key in (
            ("plan_path", "plan_sha256"),
            ("manifest_path", "manifest_sha256"),
            ("target_records_path", "target_records_sha256"),
        ):
            if _sha256(Path(source[path_key])) != source[hash_key]:
                raise ValueError(f"numeric root-cause source changed:{path_key}")
        _verify_diagnostic_source(source)


def prepare(args: argparse.Namespace) -> None:
    output_dir = Path(args.output_dir).resolve()
    population_path = Path(args.population_report_path).resolve()
    population = _read_json(population_path)
    population_hash = _replay_hash(
        population,
        field="report_hash",
        prefix="finance_gradient_calibration_population:",
    )
    if population.get("population_version") != POPULATION_VERSION:
        raise ValueError("numeric root-cause population version differs")
    if population.get("status") != "passed":
        raise ValueError("numeric root-cause population did not pass")
    if population.get("sealed_candidate_outcomes_observed") is not False:
        raise ValueError("numeric root-cause population observed sealed outcomes")
    partitions = population.get("partitions")
    if not isinstance(partitions, dict) or set(partitions) != {
        "development",
        "validation",
        "sealed_candidate",
    }:
        raise ValueError("numeric root-cause requires three frozen partitions")
    expected_task_ids = {
        split: {str(value) for value in partitions[split]["task_ids"]} for split in SPLITS
    }
    sources = {
        "development": _diagnostic_source_descriptor(
            _source_descriptor(
                Path(args.development_source_run_dir),
                split="development",
                expected_task_ids=expected_task_ids["development"],
            )
        ),
        "validation": _diagnostic_source_descriptor(
            _source_descriptor(
                Path(args.validation_source_run_dir),
                split="validation",
                expected_task_ids=expected_task_ids["validation"],
            )
        ),
    }
    if sources["development"]["model_dir"] != sources["validation"]["model_dir"]:
        raise ValueError("numeric root-cause source models differ")
    if (
        sources["development"]["beneficiary_adapter_tensor_sha256"]
        != sources["validation"]["beneficiary_adapter_tensor_sha256"]
    ):
        raise ValueError("numeric root-cause beneficiary checkpoints differ")
    for key in ("task_id", "record_id", "gradient_seed"):
        left = {str(row[key]) for row in sources["development"]["jobs"]}
        right = {str(row[key]) for row in sources["validation"]["jobs"]}
        if left & right:
            raise ValueError(f"numeric root-cause {key} partitions overlap")
    if set(sources["development"]["objective_record_ids"]) & set(
        sources["validation"]["objective_record_ids"]
    ):
        raise ValueError("numeric root-cause objective records overlap")

    implementation_manifest = _implementation_manifest()
    plan: dict[str, Any] = {
        "root_cause_version": ROOT_CAUSE_VERSION,
        "source_gradient_version": GRADIENT_ALIGNMENT_VERSION,
        "population_report_path": str(population_path),
        "population_report_sha256": _sha256(population_path),
        "population_report_hash": population_hash,
        "population_partition_ids": {
            name: partitions[name]["task_set_id"]
            for name in ("development", "validation", "sealed_candidate")
        },
        "sources": sources,
        "profiles": tuple(asdict(value) for value in ROOT_CAUSE_PROFILES),
        "profile_manifest_hash": PROFILE_MANIFEST_HASH,
        "profile_factor_changes": _serialized_factor_changes(),
        "profile_resource_contracts": PROFILE_RESOURCE_CONTRACTS,
        "implementation_sha256": _sha256(Path(__file__).resolve()),
        "implementation_manifest": implementation_manifest,
        "implementation_manifest_hash": canonical_hash(
            implementation_manifest,
            prefix="finance_gradient_numeric_root_cause_implementation:",
        ),
        "fixed_numeric_thresholds": FIXED_NUMERIC_THRESHOLDS,
        "selection_policy": SELECTION_POLICY,
        "contrast_policy": {
            "pairing_key": "job_id",
            "cluster_key": "task_id",
            "bootstrap_seed": 20260873,
            "bootstrap_replicates": 2000,
            "factor_baselines": {
                profile.profile_id: profile.baseline_profile_id
                for profile in ROOT_CAUSE_PROFILES
                if profile.baseline_profile_id is not None
            },
        },
        "validation_blinding_policy": (
            "validation_profile_runs_only_after_root_cause_selection_is_frozen"
        ),
        "sealed_candidate_policy": "sealed_candidate_is_not_a_root_cause_input",
        "production_effect": "none_until_independent_validation_passes",
        "claim_boundary": (
            "This plan diagnoses first-order numerical decomposition only. "
            "It cannot authorize Contribution, GP-C, or a VTDO update."
        ),
    }
    plan["plan_hash"] = canonical_hash(
        plan,
        prefix="finance_gradient_numeric_root_cause_plan:",
    )
    output_dir.mkdir(parents=True, exist_ok=True)
    plan_path = output_dir / "plan.json"
    if plan_path.exists():
        existing = _read_json(plan_path)
        if existing != plan:
            raise ValueError("numeric root-cause output directory contains another plan")
    else:
        _write_json(plan_path, plan)
    print(json.dumps(plan, ensure_ascii=False, indent=2, sort_keys=True))


def _gpu_memory_snapshot(torch_module: Any, gpu_ids: tuple[int, ...]) -> dict[str, dict[str, int]]:
    values: dict[str, dict[str, int]] = {}
    for gpu_id in gpu_ids:
        free_bytes, total_bytes = torch_module.cuda.mem_get_info(gpu_id)
        values[str(gpu_id)] = {
            "free_bytes": int(free_bytes),
            "total_bytes": int(total_bytes),
            "allocated_bytes": int(torch_module.cuda.memory_allocated(gpu_id)),
            "reserved_bytes": int(torch_module.cuda.memory_reserved(gpu_id)),
        }
    return values


def _verify_resource_contract(
    profile: RootCauseProfile,
    gpu_ids: tuple[int, ...],
    snapshot: dict[str, dict[str, int]],
) -> dict[str, int]:
    contract = PROFILE_RESOURCE_CONTRACTS[profile.profile_id]
    if len(gpu_ids) != int(contract["required_gpu_count"]):
        raise ValueError(
            f"numeric root-cause profile requires {contract['required_gpu_count']} GPU(s)"
        )
    if len(set(gpu_ids)) != len(gpu_ids):
        raise ValueError("numeric root-cause GPU ids are duplicated")
    if set(snapshot) != {str(value) for value in gpu_ids}:
        raise ValueError("numeric root-cause GPU snapshot differs")
    if any(
        int(row["free_bytes"]) < int(contract["minimum_free_memory_bytes_per_gpu"])
        for row in snapshot.values()
    ):
        raise ValueError("numeric root-cause GPU free-memory preflight failed")
    return contract


def _verify_result(
    result: dict[str, Any],
    plan: dict[str, Any],
    *,
    split: str,
    profile_id: str,
    uncertainty_envelope: float | None = None,
) -> None:
    if result.get("root_cause_version") != ROOT_CAUSE_VERSION:
        raise ValueError("numeric root-cause result version differs")
    if result.get("plan_hash") != plan["plan_hash"]:
        raise ValueError("numeric root-cause result crosses plans")
    if result.get("split") != split:
        raise ValueError("numeric root-cause result crosses splits")
    profile = _profile(profile_id)
    if result.get("profile") != asdict(profile):
        raise ValueError("numeric root-cause result profile differs")
    if result.get("profile_algorithm_contract") != profile.algorithm_contract:
        raise ValueError("numeric root-cause algorithm contract differs")
    if result.get("resource_contract") != PROFILE_RESOURCE_CONTRACTS[profile_id]:
        raise ValueError("numeric root-cause result resource contract differs")
    if result.get("implementation_sha256") != plan.get("implementation_sha256"):
        raise ValueError("numeric root-cause result implementation differs")
    if result.get("implementation_manifest_hash") != plan.get("implementation_manifest_hash"):
        raise ValueError("numeric root-cause result dependency manifest differs")
    if result.get("applied_uncertainty_envelope") != uncertainty_envelope:
        raise ValueError("numeric root-cause result uncertainty envelope differs")
    source = plan["sources"][split]
    for field in (
        "source_plan_hash",
        "source_manifest_hash",
        "objective_split",
        "objective_record_set_id",
    ):
        source_field = field.replace("source_", "") if field.startswith("source_") else field
        if result.get(field) != source[source_field]:
            raise ValueError(f"numeric root-cause result source differs:{field}")
    status = result.get("status")
    if status not in {"completed", "resource_capacity_failed", "execution_failed"}:
        raise ValueError("numeric root-cause result status is invalid")
    gpu_ids_value = result.get("requested_cuda_device_ids")
    preflight = result.get("preflight_gpu_memory")
    if not isinstance(gpu_ids_value, (list, tuple)) or not isinstance(preflight, dict):
        raise ValueError("numeric root-cause result resource preflight is missing")
    gpu_ids = tuple(int(value) for value in gpu_ids_value)
    _verify_resource_contract(profile, gpu_ids, preflight)
    if status == "completed":
        rows = result.get("rows")
        if not isinstance(rows, list) or len(rows) != len(source["jobs"]):
            raise ValueError("numeric root-cause completed row matrix differs")
        identity_fields = (
            "job_id",
            "task_id",
            "task_type",
            "state_id",
            "record_id",
            "gradient_seed",
        )
        for row, job in zip(rows, source["jobs"], strict=True):
            if not isinstance(row, dict) or any(
                row.get(field) != job.get(field) for field in identity_fields
            ):
                raise ValueError("numeric root-cause completed row identity differs")
        checkpoint_hashes = result.get("checkpoint_hashes")
        if result.get("checkpoint_version") != CHECKPOINT_VERSION:
            raise ValueError("numeric root-cause result checkpoint version differs")
        if (
            not isinstance(checkpoint_hashes, (list, tuple))
            or len(checkpoint_hashes) != len(rows)
            or len({str(value) for value in checkpoint_hashes}) != len(rows)
            or any(not str(value).strip() for value in checkpoint_hashes)
        ):
            raise ValueError("numeric root-cause result checkpoint lineage differs")
        expected_summary = _combined_summary(
            rows,
            task_distributions=source["task_distributions"],
            raw_thresholds=FIXED_NUMERIC_THRESHOLDS,
            uncertainty_envelope=uncertainty_envelope,
        )
        if canonical_hash(result.get("summary")) != canonical_hash(expected_summary):
            raise ValueError("numeric root-cause result summary replay differs")
    elif any(field in result for field in ("rows", "summary", "checkpoint_hashes")):
        raise ValueError("numeric root-cause failed result contains completed payload")
    _replay_hash(
        result,
        field="result_hash",
        prefix="finance_gradient_numeric_root_cause_result:",
    )


def run_profile(args: argparse.Namespace) -> None:
    import torch

    output_dir = Path(args.output_dir).resolve()
    plan = _read_json(output_dir / "plan.json")
    _verify_plan(plan)
    split = str(args.split)
    if split not in SPLITS:
        raise ValueError("unknown numeric root-cause split")
    profile = _profile(str(args.profile_id))
    result_path = output_dir / split / f"{profile.profile_id}.json"
    if result_path.exists():
        raise ValueError("numeric root-cause result already exists and is immutable")
    if split == "validation":
        selection_path = output_dir / "selection.json"
        if not selection_path.is_file():
            raise ValueError("numeric root-cause validation cannot run before selection")
        selection = _read_json(selection_path)
        _verify_selection(selection, plan, output_dir=output_dir)
        if selection.get("status") != "frozen":
            raise ValueError("numeric root-cause has no frozen validation profile")
        if selection.get("selected_profile_id") != profile.profile_id:
            raise ValueError("numeric root-cause validation profile differs from selection")
        uncertainty_envelope = float(selection["pairwise_uncertainty_envelope"])
    else:
        uncertainty_envelope = None

    gpu_ids = tuple(int(value) for value in args.gpu_ids)
    if any(value < 0 or value >= torch.cuda.device_count() for value in gpu_ids):
        raise ValueError("numeric root-cause GPU id is not visible")
    torch.cuda.set_device(gpu_ids[0])
    snapshot = _gpu_memory_snapshot(torch, gpu_ids)
    resource_contract = _verify_resource_contract(profile, gpu_ids, snapshot)
    for gpu_id in gpu_ids:
        torch.cuda.reset_peak_memory_stats(gpu_id)
    _seed_everything(20260873)
    _configure_numeric_policy(profile.precision)
    source = plan["sources"][split]
    tokenizer = _load_tokenizer(Path(source["model_dir"]))
    started = time.monotonic()
    result: dict[str, Any] = {
        "root_cause_version": ROOT_CAUSE_VERSION,
        "plan_hash": plan["plan_hash"],
        "split": split,
        "implementation_sha256": plan["implementation_sha256"],
        "implementation_manifest_hash": plan["implementation_manifest_hash"],
        "applied_uncertainty_envelope": uncertainty_envelope,
        "profile": asdict(profile),
        "profile_algorithm_contract": profile.algorithm_contract,
        "source_plan_hash": source["plan_hash"],
        "source_manifest_hash": source["manifest_hash"],
        "objective_split": source["objective_split"],
        "objective_record_set_id": source["objective_record_set_id"],
        "requested_cuda_device_ids": gpu_ids,
        "resource_contract": resource_contract,
        "preflight_gpu_memory": snapshot,
        "cuda_visible_devices_env": os.environ.get("CUDA_VISIBLE_DEVICES"),
    }
    model: Any | None = None
    try:
        model, device_map = _load_calibration_model(
            model_dir=Path(source["model_dir"]),
            adapter_dir=Path(source["beneficiary_adapter_dir"]),
            profile=profile.precision,
            gpu_ids=gpu_ids,
        )
        if _adapter_tensor_sha256(model) != source["beneficiary_adapter_tensor_sha256"]:
            raise ValueError("numeric root-cause loaded another beneficiary Adapter")
        source_manifest = _read_json(Path(source["manifest_path"]))
        parameter_manifest, parameter_manifest_hash = _gradient_parameter_manifest(model)
        if parameter_manifest != source_manifest["parameter_manifest"]:
            raise ValueError("numeric root-cause parameter manifest differs")
        if parameter_manifest_hash != source_manifest["parameter_manifest_hash"]:
            raise ValueError("numeric root-cause parameter identity differs")
        _, objective_gradients = _load_gradient_artifacts(source_manifest)
        objective = objective_gradients[source["objective_split"]]
        objective_norm = _gradient_norm(objective)
        records = _load_records(Path(source["target_records_path"]))
        checkpoints = _load_checkpoints(
            output_dir,
            plan=plan,
            source=source,
            split=split,
            profile=profile,
        )
        completed_before_resume = len(checkpoints)
        completed_now = 0
        for job in source["jobs"]:
            job_id = str(job["job_id"])
            if job_id in checkpoints:
                continue
            _seed_everything(int(job["gradient_seed"]))
            _configure_numeric_policy(profile.precision)
            regions = source["token_regions"][job["record_id"]]
            decomposition = _root_cause_decomposition(
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
            row = {
                "job_id": job["job_id"],
                "task_id": job["task_id"],
                "task_type": job["task_type"],
                "state_id": job["state_id"],
                "record_id": job["record_id"],
                "gradient_seed": int(job["gradient_seed"]),
                "full_gp_score": full_score,
                "recomposed_gp_score": recomposed_score,
                "objective_gradient_norm": objective_norm,
                **decomposition,
            }
            checkpoint = _build_checkpoint(
                plan=plan,
                source=source,
                split=split,
                profile=profile,
                job=job,
                row=row,
            )
            checkpoint_path = _checkpoint_path(
                output_dir,
                split=split,
                profile_id=profile.profile_id,
                job_id=job_id,
            )
            if checkpoint_path.exists():
                raise ValueError("numeric root-cause checkpoint appeared concurrently")
            _write_json(checkpoint_path, checkpoint)
            checkpoints[job_id] = checkpoint
            completed_now += 1
            del full, recomposed
        if len(checkpoints) != len(source["jobs"]):
            raise ValueError("numeric root-cause checkpoint matrix is incomplete")
        rows = [checkpoints[str(job["job_id"])]["row"] for job in source["jobs"]]
        checkpoint_hashes = tuple(
            str(checkpoints[str(job["job_id"])]["checkpoint_hash"]) for job in source["jobs"]
        )
        summary = _combined_summary(
            rows,
            task_distributions=source["task_distributions"],
            raw_thresholds=FIXED_NUMERIC_THRESHOLDS,
            uncertainty_envelope=uncertainty_envelope,
        )
        result.update(
            {
                "status": "completed",
                "rows": rows,
                "checkpoint_version": CHECKPOINT_VERSION,
                "checkpoint_hashes": checkpoint_hashes,
                "completed_before_resume": completed_before_resume,
                "completed_now": completed_now,
                "summary": summary,
                "resolved_hf_device_map": device_map,
                "resolved_hf_device_map_hash": canonical_hash(
                    device_map,
                    prefix="finance_gradient_numeric_root_cause_device_map:",
                ),
                "trainable_parameter_manifest": parameter_manifest,
                "trainable_parameter_manifest_hash": parameter_manifest_hash,
                "trainable_parameter_dtypes": tuple(
                    sorted({str(value["dtype"]) for value in parameter_manifest.values()})
                ),
            }
        )
        del objective_gradients, objective
        model = None
    except torch.cuda.OutOfMemoryError as error:
        result.update(
            {
                "status": "resource_capacity_failed",
                "error_type": type(error).__name__,
                "error": str(error),
                "failure_gpu_memory": _gpu_memory_snapshot(torch, gpu_ids),
            }
        )
        model = None
    except Exception as error:
        result.update(
            {
                "status": "execution_failed",
                "error_type": type(error).__name__,
                "error": str(error),
            }
        )
        model = None
    result.update(
        {
            "runtime_seconds": time.monotonic() - started,
            "peak_gpu_memory_bytes_by_requested_device": {
                str(gpu_id): int(torch.cuda.max_memory_allocated(gpu_id)) for gpu_id in gpu_ids
            },
            "torch_version": torch.__version__,
        }
    )
    result["result_hash"] = canonical_hash(
        result,
        prefix="finance_gradient_numeric_root_cause_result:",
    )
    _write_json(result_path, result)
    assert model is None
    gc.collect()
    torch.cuda.empty_cache()
    print(json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True))


def _bootstrap_interval(
    values_by_task: dict[str, list[float]],
    *,
    seed: int,
    replicates: int,
) -> tuple[float, float]:
    tasks = tuple(sorted(values_by_task))
    if not tasks:
        raise ValueError("numeric root-cause contrast has no tasks")
    task_means = {task: statistics.fmean(values_by_task[task]) for task in tasks}
    generator = random.Random(seed)
    values = []
    for _ in range(replicates):
        sample = [generator.choice(tasks) for _ in tasks]
        values.append(statistics.fmean(task_means[task] for task in sample))
    values.sort()
    return (
        values[int(0.025 * (len(values) - 1))],
        values[int(0.975 * (len(values) - 1))],
    )


def _contrast_rows(
    baseline: dict[str, Any],
    variant: dict[str, Any],
    *,
    seed: int,
    replicates: int,
) -> dict[str, Any]:
    baseline_rows = {str(row["job_id"]): row for row in baseline["rows"]}
    variant_rows = {str(row["job_id"]): row for row in variant["rows"]}
    if set(baseline_rows) != set(variant_rows):
        raise ValueError("numeric root-cause profiles do not share paired jobs")
    metric_specs = {
        "relative_error_reduction": (
            "token_gradient_recomposition_relative_error",
            1.0,
        ),
        "cosine_improvement": (
            "token_gradient_recomposition_cosine",
            -1.0,
        ),
        "gp_delta_reduction": ("gp_score_absolute_delta", 1.0),
    }
    grouped: dict[str, dict[str, list[float]]] = {name: {} for name in metric_specs}
    paired: list[dict[str, Any]] = []
    for job_id in sorted(baseline_rows):
        left = baseline_rows[job_id]
        right = variant_rows[job_id]
        if any(
            left[key] != right[key]
            for key in ("task_id", "task_type", "state_id", "record_id", "gradient_seed")
        ):
            raise ValueError("numeric root-cause paired row identity differs")
        left_gp = abs(float(left["full_gp_score"]) - float(left["recomposed_gp_score"]))
        right_gp = abs(float(right["full_gp_score"]) - float(right["recomposed_gp_score"]))
        left_values = {**left, "gp_score_absolute_delta": left_gp}
        right_values = {**right, "gp_score_absolute_delta": right_gp}
        row = {
            "job_id": job_id,
            "task_id": left["task_id"],
            "task_type": left["task_type"],
        }
        for name, (field, orientation) in metric_specs.items():
            delta = orientation * (float(left_values[field]) - float(right_values[field]))
            row[name] = delta
            grouped[name].setdefault(str(left["task_id"]), []).append(delta)
        paired.append(row)
    metrics: dict[str, Any] = {}
    for index, (name, values) in enumerate(grouped.items()):
        flat = [value for task_values in values.values() for value in task_values]
        lower, upper = _bootstrap_interval(
            values,
            seed=seed + index,
            replicates=replicates,
        )
        metrics[name] = {
            "mean": statistics.fmean(flat),
            "median": statistics.median(flat),
            "positive_fraction": sum(value > 0 for value in flat) / len(flat),
            "task_cluster_bootstrap_95": (lower, upper),
        }
    return {
        "baseline_profile_id": baseline["profile"]["profile_id"],
        "variant_profile_id": variant["profile"]["profile_id"],
        "paired_job_count": len(paired),
        "metrics": metrics,
    }


def _selection_key(result: dict[str, Any]) -> tuple[float, float, float, int, str]:
    metrics = result["summary"]["raw_numeric"]["metrics"]
    profile = _profile(str(result["profile"]["profile_id"]))
    return (
        float(metrics["maximum_gradient_recomposition_relative_error"]),
        float(metrics["maximum_gp_score_absolute_delta"]),
        -float(metrics["minimum_gradient_recomposition_cosine"]),
        profile.intervention_count,
        profile.profile_id,
    )


def _paired_contrasts(
    results: list[dict[str, Any]],
    plan: dict[str, Any],
) -> tuple[dict[str, Any], ...]:
    completed = [result for result in results if result.get("status") == "completed"]
    by_profile = {str(result["profile"]["profile_id"]): result for result in completed}
    contrasts = []
    for profile in ROOT_CAUSE_PROFILES:
        baseline_id = profile.baseline_profile_id
        if baseline_id is None:
            continue
        if baseline_id not in by_profile or profile.profile_id not in by_profile:
            continue
        contrasts.append(
            _contrast_rows(
                by_profile[baseline_id],
                by_profile[profile.profile_id],
                seed=int(plan["contrast_policy"]["bootstrap_seed"]),
                replicates=int(plan["contrast_policy"]["bootstrap_replicates"]),
            )
        )
    return tuple(contrasts)


def _verify_selection(
    selection: dict[str, Any],
    plan: dict[str, Any],
    *,
    output_dir: Path | None = None,
) -> None:
    if selection.get("root_cause_version") != ROOT_CAUSE_VERSION:
        raise ValueError("numeric root-cause selection version differs")
    if selection.get("plan_hash") != plan["plan_hash"]:
        raise ValueError("numeric root-cause selection crosses plans")
    if selection.get("fixed_numeric_thresholds") != FIXED_NUMERIC_THRESHOLDS:
        raise ValueError("numeric root-cause selection thresholds differ")
    if selection.get("selection_policy") != SELECTION_POLICY:
        raise ValueError("numeric root-cause selection policy differs")
    if selection.get("profile_manifest_hash") != PROFILE_MANIFEST_HASH:
        raise ValueError("numeric root-cause selection profile manifest differs")
    if selection.get("validation_observed") is not False:
        raise ValueError("numeric root-cause selection observed validation")
    if selection.get("sealed_candidate_outcomes_observed") is not False:
        raise ValueError("numeric root-cause selection observed sealed candidate")
    _replay_hash(
        selection,
        field="selection_hash",
        prefix="finance_gradient_numeric_root_cause_selection:",
    )
    result_hashes = selection.get("development_result_hashes")
    if (
        not isinstance(result_hashes, (list, tuple))
        or len(result_hashes) != len(ROOT_CAUSE_PROFILES)
        or len({str(value) for value in result_hashes}) != len(ROOT_CAUSE_PROFILES)
    ):
        raise ValueError("numeric root-cause selection development lineage differs")
    status = selection.get("status")
    if status not in {"frozen", "root_cause_matrix_failed"}:
        raise ValueError("numeric root-cause selection status is invalid")
    selected_profile_id = selection.get("selected_profile_id")
    if status == "frozen":
        if not isinstance(selected_profile_id, str) or selected_profile_id not in PROFILE_BY_ID:
            raise ValueError("numeric root-cause selected profile is invalid")
        if selected_profile_id not in selection.get("eligible_profile_ids", ()):
            raise ValueError("numeric root-cause selected profile is not eligible")
        if selection.get("required_profile_failures"):
            raise ValueError("numeric root-cause frozen selection has profile failures")
        if (
            selection.get("selected_resource_contract")
            != PROFILE_RESOURCE_CONTRACTS[selected_profile_id]
        ):
            raise ValueError("numeric root-cause selected resource contract differs")
        envelope = selection.get("pairwise_uncertainty_envelope")
        if (
            not isinstance(envelope, (int, float))
            or not math.isfinite(float(envelope))
            or float(envelope) < 0
        ):
            raise ValueError("numeric root-cause uncertainty envelope is invalid")
    elif any(
        selection.get(field) is not None
        for field in (
            "selected_profile_id",
            "selected_resource_contract",
            "pairwise_uncertainty_envelope",
        )
    ):
        raise ValueError("failed numeric root-cause selection exposes a profile")
    if output_dir is None:
        return
    results = []
    for profile in ROOT_CAUSE_PROFILES:
        result_path = output_dir / "development" / f"{profile.profile_id}.json"
        if not result_path.is_file():
            raise ValueError("numeric root-cause selection development matrix is missing")
        result = _read_json(result_path)
        _verify_result(
            result,
            plan,
            split="development",
            profile_id=profile.profile_id,
        )
        results.append(result)
    expected_hashes = tuple(str(result["result_hash"]) for result in results)
    if tuple(str(value) for value in result_hashes) != expected_hashes:
        raise ValueError("numeric root-cause selection result files differ")
    completed = [result for result in results if result.get("status") == "completed"]
    failures = tuple(
        {
            "profile_id": result["profile"]["profile_id"],
            "status": result["status"],
            "error_type": result.get("error_type"),
            "error": result.get("error"),
        }
        for result in results
        if result.get("status") != "completed"
    )
    eligible = [result for result in completed if result["summary"]["status"] == "passed"]
    expected_selected = min(eligible, key=_selection_key) if eligible else None
    expected_status = (
        "frozen" if expected_selected is not None and not failures else "root_cause_matrix_failed"
    )
    expected_selected_id = (
        str(expected_selected["profile"]["profile_id"])
        if expected_status == "frozen" and expected_selected is not None
        else None
    )
    if status != expected_status or selected_profile_id != expected_selected_id:
        raise ValueError("numeric root-cause selection decision replay differs")
    if canonical_hash(selection.get("required_profile_failures")) != canonical_hash(failures):
        raise ValueError("numeric root-cause selection failure replay differs")
    expected_eligible = tuple(str(result["profile"]["profile_id"]) for result in eligible)
    if tuple(selection.get("eligible_profile_ids", ())) != expected_eligible:
        raise ValueError("numeric root-cause selection eligibility replay differs")
    expected_contrasts = _paired_contrasts(results, plan)
    if canonical_hash(selection.get("paired_contrasts")) != canonical_hash(expected_contrasts):
        raise ValueError("numeric root-cause selection contrast replay differs")
    if expected_selected is not None:
        expected_envelope = float(
            expected_selected["summary"]["envelope_calibration"]["pairwise_uncertainty_envelope"]
        )
        if float(selection["pairwise_uncertainty_envelope"]) != expected_envelope:
            raise ValueError("numeric root-cause selection envelope replay differs")


def freeze_selection(args: argparse.Namespace) -> None:
    output_dir = Path(args.output_dir).resolve()
    plan = _read_json(output_dir / "plan.json")
    _verify_plan(plan)
    validation_dir = output_dir / "validation"
    if validation_dir.exists() and any(validation_dir.glob("*.json")):
        raise ValueError("numeric root-cause selection observed validation results")
    results = []
    for profile in ROOT_CAUSE_PROFILES:
        result_path = output_dir / "development" / f"{profile.profile_id}.json"
        if not result_path.is_file():
            raise ValueError("numeric root-cause development matrix is incomplete")
        result = _read_json(result_path)
        _verify_result(
            result,
            plan,
            split="development",
            profile_id=profile.profile_id,
        )
        results.append(result)
    completed = [
        result
        for result in results
        if result.get("status") == "completed" and isinstance(result.get("summary"), dict)
    ]
    required_profile_failures = tuple(
        {
            "profile_id": result["profile"]["profile_id"],
            "status": result["status"],
            "error_type": result.get("error_type"),
            "error": result.get("error"),
        }
        for result in results
        if result.get("status") != "completed"
    )
    contrasts = _paired_contrasts(results, plan)
    eligible = [result for result in completed if result["summary"]["status"] == "passed"]
    selected = min(eligible, key=_selection_key) if eligible else None
    status = (
        "frozen"
        if selected is not None and not required_profile_failures
        else "root_cause_matrix_failed"
    )
    selection: dict[str, Any] = {
        "root_cause_version": ROOT_CAUSE_VERSION,
        "plan_hash": plan["plan_hash"],
        "profile_manifest_hash": PROFILE_MANIFEST_HASH,
        "status": status,
        "selected_profile_id": (
            str(selected["profile"]["profile_id"])
            if status == "frozen" and selected is not None
            else None
        ),
        "development_result_hashes": tuple(str(result["result_hash"]) for result in results),
        "eligible_profile_ids": tuple(str(result["profile"]["profile_id"]) for result in eligible),
        "required_profile_failures": required_profile_failures,
        "paired_contrasts": tuple(contrasts),
        "selection_policy": SELECTION_POLICY,
        "fixed_numeric_thresholds": FIXED_NUMERIC_THRESHOLDS,
        "pairwise_uncertainty_envelope": (
            float(selected["summary"]["envelope_calibration"]["pairwise_uncertainty_envelope"])
            if status == "frozen" and selected is not None
            else None
        ),
        "selected_resource_contract": (
            PROFILE_RESOURCE_CONTRACTS[str(selected["profile"]["profile_id"])]
            if status == "frozen" and selected is not None
            else None
        ),
        "validation_observed": False,
        "sealed_candidate_outcomes_observed": False,
        "claim_boundary": (
            "Selection is a development-only numeric root-cause result. "
            "It does not authorize Contribution or GP-C."
        ),
    }
    selection["selection_hash"] = canonical_hash(
        selection,
        prefix="finance_gradient_numeric_root_cause_selection:",
    )
    _verify_selection(selection, plan, output_dir=output_dir)
    _write_json(output_dir / "selection.json", selection)
    print(json.dumps(selection, ensure_ascii=False, indent=2, sort_keys=True))


def aggregate(args: argparse.Namespace) -> None:
    output_dir = Path(args.output_dir).resolve()
    plan = _read_json(output_dir / "plan.json")
    _verify_plan(plan)
    selection = _read_json(output_dir / "selection.json")
    _verify_selection(selection, plan, output_dir=output_dir)
    profile_id = selection.get("selected_profile_id")
    if selection.get("status") != "frozen" or not isinstance(profile_id, str):
        raise ValueError("numeric root-cause has no independently confirmable profile")
    development = _read_json(output_dir / "development" / f"{profile_id}.json")
    validation = _read_json(output_dir / "validation" / f"{profile_id}.json")
    _verify_result(
        development,
        plan,
        split="development",
        profile_id=profile_id,
    )
    _verify_result(
        validation,
        plan,
        split="validation",
        profile_id=profile_id,
        uncertainty_envelope=float(selection["pairwise_uncertainty_envelope"]),
    )
    if development["result_hash"] not in selection["development_result_hashes"]:
        raise ValueError("numeric root-cause selected development lineage is missing")
    validation_passed = bool(
        validation.get("status") == "completed"
        and validation.get("summary", {}).get("status") == "passed"
    )
    contract_path = output_dir / "frozen_numeric_contract.json"
    if not validation_passed and contract_path.exists():
        raise ValueError("failed numeric root-cause validation has a stale contract")
    report: dict[str, Any] = {
        "root_cause_version": ROOT_CAUSE_VERSION,
        "plan_hash": plan["plan_hash"],
        "population_report_hash": plan["population_report_hash"],
        "profile_manifest_hash": PROFILE_MANIFEST_HASH,
        "selection_hash": selection["selection_hash"],
        "selected_profile": asdict(_profile(profile_id)),
        "development_result_hash": development["result_hash"],
        "validation_result_hash": validation["result_hash"],
        "development_summary": development["summary"],
        "validation_summary": validation.get("summary"),
        "paired_contrasts": selection["paired_contrasts"],
        "status": "passed" if validation_passed else "failed",
        "numeric_contract_authorized": validation_passed,
        "production_authorized": False,
        "authorization_effect": (
            "numeric_contract_frozen_for_one_inherited_sealed_candidate"
            if validation_passed
            else "none"
        ),
        "claim_boundary": (
            "A pass authorizes only the numeric decomposition profile for the inherited "
            "sealed candidate. It does not authorize Contribution, GP-C, or VTDO."
        ),
    }
    report["report_hash"] = canonical_hash(
        report,
        prefix="finance_gradient_numeric_root_cause_report:",
    )
    _write_json(output_dir / "report.json", report)
    if validation_passed:
        profile = _profile(profile_id)
        contract: dict[str, Any] = {
            "contract_version": "finance_gradient_numeric_contract.v17",
            "root_cause_version": ROOT_CAUSE_VERSION,
            "plan_hash": plan["plan_hash"],
            "population_report_hash": plan["population_report_hash"],
            "sealed_candidate_task_set_id": plan["population_partition_ids"]["sealed_candidate"],
            "selection_hash": selection["selection_hash"],
            "selected_profile": asdict(profile),
            "profile_algorithm_contract": profile.algorithm_contract,
            "fixed_numeric_thresholds": FIXED_NUMERIC_THRESHOLDS,
            "pairwise_uncertainty_envelope": selection["pairwise_uncertainty_envelope"],
            "development_result_hash": development["result_hash"],
            "validation_result_hash": validation["result_hash"],
            "allowed_next_run_role": "independent_sealed_candidate",
            "production_effect": "none_until_sealed_candidate_passes",
        }
        contract["contract_hash"] = canonical_hash(
            contract,
            prefix="finance_gradient_numeric_contract:",
        )
        _write_json(contract_path, contract)
    print(json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True))


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Diagnose Finance Gradient Projection numeric fidelity"
    )
    subparsers = parser.add_subparsers(dest="command", required=True)
    prepare_parser = subparsers.add_parser("prepare")
    prepare_parser.add_argument("--population-report-path", required=True)
    prepare_parser.add_argument("--development-source-run-dir", required=True)
    prepare_parser.add_argument("--validation-source-run-dir", required=True)
    prepare_parser.add_argument("--output-dir", required=True)
    prepare_parser.set_defaults(handler=prepare)
    run_parser = subparsers.add_parser("run-profile")
    run_parser.add_argument("--output-dir", required=True)
    run_parser.add_argument("--split", choices=SPLITS, required=True)
    run_parser.add_argument("--profile-id", required=True)
    run_parser.add_argument("--gpu-ids", nargs="+", type=int, required=True)
    run_parser.set_defaults(handler=run_profile)
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
