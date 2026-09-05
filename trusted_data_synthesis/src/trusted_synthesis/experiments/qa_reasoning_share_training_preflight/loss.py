"""Deterministic CPU collation and an actually applied, causally shifted weighted loss.

No Student model is constructed. Controlled token NLLs exercise the aggregation
interface, not a model forward pass, utility estimate, or parameter update.
"""

from __future__ import annotations

import io
import zipfile
from fractions import Fraction
from typing import Any

import numpy as np
import torch

from .models import LABEL_IGNORE_INDEX, as_fraction, fraction_record, record, require, sha


def encode_arrays(arrays: dict[str, Any]) -> bytes:
    """Stable NPZ bytes: explicit order, dtype, ZIP metadata, no pickle/timestamp."""
    output = io.BytesIO()
    with zipfile.ZipFile(output, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=9) as archive:
        for name, value in sorted(arrays.items()):
            payload = io.BytesIO()
            np.lib.format.write_array(payload, np.ascontiguousarray(value), allow_pickle=False)
            info = zipfile.ZipInfo(name + ".npy", date_time=(1980, 1, 1, 0, 0, 0))
            info.compress_type = zipfile.ZIP_DEFLATED
            info.external_attr = 0o600 << 16
            archive.writestr(info, payload.getvalue(), compresslevel=9)
    return output.getvalue()


def decode_arrays(data: bytes) -> dict[str, Any]:
    with np.load(io.BytesIO(data), allow_pickle=False) as bundle:
        return {key: bundle[key] for key in bundle.files}


def collate(
    tokens: dict[str, Any], pad_token_id: int
) -> tuple[dict[str, Any], dict[str, Any], bytes]:
    rows = tokens["rows"]
    length = max(row["sequence_length"] for row in rows)
    shape = (len(rows), length)
    arrays = {
        "input_ids": np.full(shape, pad_token_id, dtype=np.int64),
        "labels": np.full(shape, LABEL_IGNORE_INDEX, dtype=np.int64),
        "attention_mask": np.zeros(shape, dtype=np.int8),
        "target_mask": np.zeros(shape, dtype=np.int8),
    }
    for index, row in enumerate(rows):
        count = row["sequence_length"]
        for name in arrays:
            require(len(row[name]) == count, "loss.row_array_length")
            arrays[name][index, :count] = row[name]
    binary = encode_arrays(arrays)
    summary = record(
        "base_batch",
        tokenized_dataset_id=tokens["id"],
        row_ids=[row["row_id"] for row in rows],
        shape=list(shape),
        padding_side="right",
        pad_token_id=pad_token_id,
        array_dtypes={name: str(value.dtype) for name, value in arrays.items()},
        npz_sha256=sha(binary),
        npz_byte_count=len(binary),
        real_token_count=int(arrays["attention_mask"].sum()),
        target_token_count=int(arrays["target_mask"].sum()),
        padding_token_count=int(np.prod(shape) - arrays["attention_mask"].sum()),
        target_excludes_prompt_suffix_padding=True,
        truncated=False,
        shared_by_views=["P", "Q"],
    )
    return summary, arrays, binary


def coefficient_array(view: dict[str, Any], arrays: dict[str, Any]) -> Any:
    coefficients = np.array(
        [float(as_fraction(row["token_coefficient"])) for row in view["row_weights"]],
        dtype=np.float64,
    )
    require(len(coefficients) == arrays["target_mask"].shape[0], "loss.weight_row_count")
    return coefficients[:, None] * arrays["target_mask"][:, 1:]


def aggregate_loss(
    token_nll: torch.Tensor, labels: torch.Tensor, coefficients: torch.Tensor
) -> torch.Tensor:
    """NLL[i,t] predicts labels[i,t+1]; return the fixed objective's SUM.

    Caller supplies unreduced per-token losses. A later model integration must
    produce those losses itself and register its optimization protocol separately.
    """
    require(token_nll.ndim == labels.ndim == coefficients.ndim == 2, "loss.causal_rank")
    require(
        token_nll.device.type == labels.device.type == coefficients.device.type == "cpu",
        "loss.cpu_only",
    )
    require(token_nll.shape == coefficients.shape == labels[:, 1:].shape, "loss.causal_shapes")
    mask = labels[:, 1:] != LABEL_IGNORE_INDEX
    require(bool(torch.all(coefficients[~mask] == 0)), "loss.non_target_weight")
    require(
        bool(torch.all(torch.isfinite(coefficients))) and bool(torch.all(coefficients >= 0)),
        "loss.invalid_coefficient",
    )
    require(
        bool(torch.all(torch.isfinite(token_nll[mask]))) and bool(torch.all(token_nll[mask] >= 0)),
        "loss.invalid_active_nll",
    )
    safe_loss = torch.where(mask, token_nll, torch.zeros_like(token_nll))
    return (safe_loss * coefficients).sum()


def run_loss_checks(
    dataset: dict[str, Any],
    tokens: dict[str, Any],
    kernel: dict[str, Any],
    batch: dict[str, Any],
    arrays: dict[str, Any],
    views: list[dict[str, Any]],
) -> tuple[dict[str, Any], dict[str, bytes]]:
    """Compare CPU aggregation to exact Fraction calculations over controlled NLLs."""
    rows = dataset["rows"]
    labels = torch.from_numpy(arrays["labels"])
    mask = arrays["target_mask"][:, 1:].astype(bool)
    shape = mask.shape
    require(not torch.cuda.is_initialized(), "loss.cuda_preinitialized")
    states = [item["state_id"] for item in kernel["state_support"]]
    sessions = [item["session_id"] for item in kernel["trajectories"]]
    scenarios = [
        ("all_one", None),
        *[("class_indicator", value) for value in states],
        *[("trajectory_indicator", value) for value in sessions],
        ("position_varying", None),
    ]
    results = []
    weight_binaries = {}
    for view in views:
        coefficients = coefficient_array(view, arrays)
        binary = encode_arrays({"causal_token_coefficients": coefficients})
        weight_binaries[view["name"]] = binary
        coefficient_tensor = torch.from_numpy(coefficients)
        for scenario, selected in scenarios:
            nll = np.full(shape, np.nan, dtype=np.float64)
            expected = Fraction(0)
            for row_index, row in enumerate(rows):
                positions = np.flatnonzero(mask[row_index])
                omega = as_fraction(view["row_weights"][row_index]["token_coefficient"])
                if scenario == "position_varying":
                    numerators = [
                        (row_index + 1) * 7 + (int(position) % 13) for position in positions
                    ]
                    nll[row_index, positions] = np.array(numerators, dtype=np.float64) / 17
                    expected += omega * Fraction(sum(numerators), 17)
                else:
                    value = int(
                        scenario == "all_one"
                        or (scenario == "class_indicator" and row["state_id"] == selected)
                        or (scenario == "trajectory_indicator" and row["session_id"] == selected)
                    )
                    nll[row_index, positions] = value
                    expected += omega * value * len(positions)
            tensor = torch.from_numpy(nll)
            actual = float(aggregate_loss(tensor, labels, coefficient_tensor))
            chunks = [slice(0, 8), slice(8, 19), slice(19, len(rows))]
            microbatch = sum(
                float(aggregate_loss(tensor[part], labels[part], coefficient_tensor[part]))
                for part in chunks
            )
            error, micro_error = abs(actual - float(expected)), abs(microbatch - float(expected))
            require(error <= 1e-12 and micro_error <= 1e-12, "loss.controlled_objective_mismatch")
            results.append(
                {
                    "view": view["name"],
                    "scenario": scenario,
                    "selected_id": selected,
                    "expected": fraction_record(expected),
                    "actual_float64": actual,
                    "absolute_error": error,
                    "fixed_coefficient_microbatch_sum": microbatch,
                    "microbatch_absolute_error": micro_error,
                    "passed": True,
                }
            )
    return record(
        "loss_checks",
        dataset_id=dataset["id"],
        tokenized_dataset_id=tokens["id"],
        kernel_id=kernel["id"],
        base_batch_id=batch["id"],
        view_ids=[view["id"] for view in views],
        checks=results,
        check_count=len(results),
        passed=all(item["passed"] for item in results),
        weight_bundles=[
            {
                "view": name,
                "relative_path": "weights/" + name + ".npz",
                "sha256": sha(data),
                "byte_count": len(data),
            }
            for name, data in weight_binaries.items()
        ],
        causal_shift=1,
        floating_dtype="float64",
        absolute_tolerance="1e-12",
        masked_nlls_are_nan_and_ignored=True,
        CPU_tensor_aggregation_executed=True,
        Student_model_loaded=False,
        Student_forward_passes=0,
        backward_calls=0,
        optimizer_steps=0,
        CUDA_initialized=torch.cuda.is_initialized(),
        GPU_jobs=0,
        controlled_losses_are_not_Student_losses=True,
        utility_or_Contribution_measured=False,
        microbatch_check_is_fixed_sum_identity_not_optimizer_equivalence=True,
    ), weight_binaries
