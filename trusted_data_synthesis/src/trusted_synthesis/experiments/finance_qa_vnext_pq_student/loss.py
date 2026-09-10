"""Fixed-coefficient target NLL sums, with exactly one causal label alignment.

Selecting the needed predecessor logits saves memory but changes neither the
supervised tokens nor their loss. No row/global mean is applied after weighting.
Synthetic logits are sufficient to check this code; it loads no Student model.
"""

import math
from fractions import Fraction

import torch
import torch.nn.functional as functional

from .plan import require
from .weights import ARMS, fraction, validate_weights


def _coefficient(value):
    require(
        isinstance(value, (str, int, float, Fraction)) and not isinstance(value, bool),
        "loss.fixed_scalar_coefficient",
    )
    try:
        exact = Fraction(str(value)) if isinstance(value, float) else Fraction(value)
        numeric = float(exact)
    except (ValueError, OverflowError, ZeroDivisionError):
        raise ValueError("loss.fixed_scalar_coefficient") from None
    require(
        exact > 0 and math.isfinite(numeric) and numeric > 0, "loss.positive_finite_coefficient"
    )
    return numeric


def _integers(values, device):
    if isinstance(values, torch.Tensor):
        require(
            values.dtype in {torch.int64, torch.int32, torch.int16, torch.int8, torch.uint8},
            "loss.integer_targets",
        )
        return values.to(device=device, dtype=torch.long)
    require(
        isinstance(values, (list, tuple)) and all(type(value) is int for value in values),
        "loss.integer_targets",
    )
    return torch.tensor(values, device=device, dtype=torch.long)


def selected_target_loss(logits, target_ids, coefficient):
    """Return float32 ``sum(CE(logits_u, target_u)) * coefficient``.

    ``logits`` is [number_of_targets, vocabulary] or [1, number_of_targets,
    vocabulary]. Its rows must already be the actual predecessor positions of the
    stored non-ignored labels. Targets must not be shifted again by this function.
    The coefficient is a fixed w(package)/L(package), shared by both original rows.
    """
    require(isinstance(logits, torch.Tensor) and logits.is_floating_point(), "loss.floating_logits")
    if logits.ndim == 3:
        require(logits.shape[0] == 1, "loss.single_original_row")
        logits = logits[0]
    require(
        logits.ndim == 2 and logits.shape[0] > 0 and logits.shape[1] > 1,
        "loss.selected_logits_shape",
    )
    targets = _integers(target_ids, logits.device)
    require(targets.ndim == 1 and targets.numel() == logits.shape[0], "loss.one_target_per_logit")
    require(
        bool(((targets >= 0) & (targets < logits.shape[-1])).all()),
        "loss.selected_targets_are_not_ignored",
    )
    scale = _coefficient(coefficient)
    loss = functional.cross_entropy(logits.float(), targets, reduction="sum") * scale
    require(bool(torch.isfinite(loss.detach())), "loss.nonfinite_active_logits")
    return loss


def full_causal_loss(logits, labels, coefficient):
    """Small-check/reference interface over one full sequence, using stored labels once."""
    require(isinstance(logits, torch.Tensor), "loss.tensor_logits")
    if logits.ndim == 3:
        require(logits.shape[0] == 1, "loss.single_original_row")
        logits = logits[0]
    require(logits.ndim == 2 and logits.shape[0] >= 2, "loss.full_logits_shape")
    targets = _integers(labels, logits.device)
    if targets.ndim == 2:
        require(targets.shape[0] == 1, "loss.single_original_label_row")
        targets = targets[0]
    require(
        targets.ndim == 1 and targets.numel() == logits.shape[0] and targets[0].item() == -100,
        "loss.full_label_shape_and_first_position",
    )
    positions = torch.where(targets != -100)[0]
    require(positions.numel() > 0 and positions[0].item() > 0, "loss.causal_target_predecessors")
    return selected_target_loss(logits[positions - 1], targets[positions], coefficient)


def _simulated_rows(view, per_row_target_nll):
    validate_weights(view)
    require(
        isinstance(per_row_target_nll, dict)
        and set(per_row_target_nll) == {row["row_index"] for row in view["rows"]},
        "loss.simulated_complete_row_set",
    )
    values = {}
    for row in view["rows"]:
        supplied = per_row_target_nll[row["row_index"]]
        require(
            isinstance(supplied, (list, tuple)) and len(supplied) == row["target_token_count"],
            "loss.simulated_original_target_count",
        )
        values[row["row_index"]] = [fraction(value) for value in supplied]
        require(all(value >= 0 for value in values[row["row_index"]]), "loss.nonnegative_nll")
    return values


def simulated_objective(view, per_row_target_nll, arm, *, row_indices=None):
    """Exact Fraction probe; fixed-coefficient blocks add without block renormalization."""
    require(arm in ARMS, "loss.P_or_Q")
    values = _simulated_rows(view, per_row_target_nll)
    indices = list(values) if row_indices is None else list(row_indices)
    require(
        len(indices) == len(set(indices)) and set(indices).issubset(values),
        "loss.simulated_unique_block_rows",
    )
    total = Fraction()
    by_index = {row["row_index"]: row for row in view["rows"]}
    for index in indices:
        total += sum(values[index], Fraction()) * fraction(by_index[index]["coefficient"][arm])
    return total


def package_mean_losses(view, per_row_target_nll):
    """Independent grouping of the same probes into the specified whole-package means."""
    values = _simulated_rows(view, per_row_target_nll)
    return {
        package["session_label"]: sum(
            (sum(values[index], Fraction()) for index in package["row_indices"]), Fraction()
        )
        / package["target_token_count"]
        for package in view["packages"]
    }
