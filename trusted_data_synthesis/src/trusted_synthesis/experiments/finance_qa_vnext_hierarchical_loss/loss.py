"""Whole-package-normalized layered NLL, never a trajectory probability.

Layer denominators count all original target tokens of the package, not one
row or a mini-batch. The caller applies the class mean or pi/(5*n) exactly
once. Original history and the causal predecessor selection are unchanged.
"""

import copy
import json
import math
from dataclasses import dataclass, field
from fractions import Fraction

import torch
import torch.nn.functional as functional

from ..finance_qa_vnext_basis_student.kernel import validate_row
from ..finance_qa_vnext_pq_student.loss import selected_target_loss
from . import protocol as p


def _fraction(value, *, allow_zero):
    p.require(
        not isinstance(value, bool) and isinstance(value, (int, float, str, Fraction)),
        "hierarchical_loss.numeric_coefficient",
    )
    try:
        result = Fraction(str(value)) if isinstance(value, float) else Fraction(value)
        numeric = float(result)
    except (ValueError, OverflowError, ZeroDivisionError):
        raise ValueError("hierarchical_loss.finite_coefficient") from None
    p.require(
        math.isfinite(numeric)
        and (result >= 0 if allow_zero else result > 0)
        and (result == 0 or numeric > 0),
        "hierarchical_loss.finite_nonnegative_coefficient",
    )
    return result


@dataclass(frozen=True, slots=True)
class HierarchicalTrajectoryLoss:
    objective: str = "hierarchical"
    profile: str = "public_rtf"
    _weights: tuple = field(init=False, repr=False)
    _policy_bytes: bytes = field(init=False, repr=False)

    def __post_init__(self):
        p.require(self.objective in p.OBJECTIVES, "hierarchical_loss.two_fixed_objectives")
        p.require(self.profile in p.PROFILES, "hierarchical_loss.fixed_public_profile")
        frozen = p.policy(self.profile)
        object.__setattr__(self, "_policy_bytes", p.encode(frozen))
        object.__setattr__(
            self, "_weights", tuple(Fraction(frozen["weights"][layer]) for layer in p.LAYERS)
        )

    def describe(self):
        return p.record(
            "trajectory_loss_configuration",
            objective=self.objective,
            profile=self.profile,
            fixed_layer_weights={
                layer: str(value) for layer, value in zip(p.LAYERS, self._weights, strict=True)
            },
            sum_hierarchical_layer_weights=str(sum(self._weights, Fraction())),
            policy=json.loads(self._policy_bytes),
            original_full_baseline=self.objective == "full_token_mean",
            inputs_are_original_supervised_tokens=True,
            class_or_state_probability_included=False,
            uses_complete_package_layer_denominators=True,
            row_mean_or_additional_whole_package_divisor=False,
            defines_feedback_log_probability=False,
        )

    def token_coefficients(self, package, annotation):
        """Return one exact Fraction per *original selected* token, in row order."""
        from .representation import validate_package_annotation

        annotation = validate_package_annotation(package, annotation)
        p.require(annotation["profile"] == self.profile, "hierarchical_loss.common_frozen_profile")
        rows = [validate_row(row) for row in package["rows"]]
        p.require(
            rows and len(rows) == len(annotation["rows"]), "hierarchical_loss.all_original_rows"
        )
        counts = {layer: 0 for layer in p.LAYERS}
        for row, annotated in zip(rows, annotation["rows"], strict=True):
            masks = annotated["layer_masks"]
            p.require(set(masks) == set(p.LAYERS), "hierarchical_loss.exact_three_layers")
            for layer in p.LAYERS:
                mask = masks[layer]
                p.require(
                    isinstance(mask, list)
                    and len(mask) == len(row["target_mask"])
                    and all(type(value) is int and value in (0, 1) for value in mask),
                    "hierarchical_loss.original_length_binary_masks",
                )
                counts[layer] += sum(mask)
            p.require(
                all(
                    sum(masks[layer][index] for layer in p.LAYERS) == value
                    for index, value in enumerate(row["target_mask"])
                ),
                "hierarchical_loss.disjoint_exhaustive_targets_no_context",
            )
        length = sum(row["target_token_count"] for row in rows)
        p.require(
            length == package["whole_package_target_tokens"] == sum(counts.values())
            and counts == annotation["layer_token_counts"],
            "hierarchical_loss.original_whole_package_counts",
        )
        # Enforce the same pair eligibility before either objective runs. A
        # missing weighted layer never becomes a baseline-only selected package.
        p.require(
            all(
                counts[layer] > 0
                for layer, weight in zip(p.LAYERS, self._weights, strict=True)
                if weight > 0
            ),
            "hierarchical_loss.missing_positive_layer_blocks_common_pair",
        )
        p.require(
            self.profile != "public_tf" or counts["reasoning"] == 0,
            "hierarchical_loss.TF_profile_cannot_hide_available_reasoning",
        )
        values = []
        for row, annotated in zip(rows, annotation["rows"], strict=True):
            coefficients = []
            for index, selected in enumerate(row["target_mask"]):
                if not selected:
                    continue
                if self.objective == "full_token_mean":
                    coefficient = Fraction(1, length)
                else:
                    layer_index = next(
                        number
                        for number, layer in enumerate(p.LAYERS)
                        if annotated["layer_masks"][layer][index]
                    )
                    coefficient = self._weights[layer_index] / counts[p.LAYERS[layer_index]]
                coefficients.append(coefficient)
            values.append(coefficients)
        expected = Fraction(1) if self.objective == "full_token_mean" else sum(self._weights)
        p.require(
            sum((sum(row, Fraction()) for row in values), Fraction()) == expected,
            "hierarchical_loss.exact_package_weight_mass",
        )
        return values

    def row_loss(self, logits, labels, coefficients, *, scale=Fraction(1)):
        """Selected predecessor logits only; no extra shift, averaging or pi."""
        p.require(
            isinstance(logits, torch.Tensor) and logits.is_floating_point(),
            "hierarchical_loss.floating_logits",
        )
        if logits.ndim == 3:
            p.require(logits.shape[0] == 1, "hierarchical_loss.one_original_row")
            logits = logits[0]
        p.require(
            logits.ndim == 2 and logits.shape[0] > 0 and logits.shape[1] > 1,
            "hierarchical_loss.selected_logits_shape",
        )
        if isinstance(labels, torch.Tensor):
            p.require(
                labels.dtype in {torch.uint8, torch.int8, torch.int16, torch.int32, torch.int64},
                "hierarchical_loss.integer_labels",
            )
            targets = labels.to(device=logits.device, dtype=torch.long)
        else:
            p.require(
                isinstance(labels, (list, tuple)) and all(type(value) is int for value in labels),
                "hierarchical_loss.integer_labels",
            )
            targets = torch.tensor(labels, device=logits.device, dtype=torch.long)
        p.require(
            targets.ndim == 1
            and len(targets) == logits.shape[0]
            and bool(((targets >= 0) & (targets < logits.shape[1])).all()),
            "hierarchical_loss.exact_selected_targets_no_ignored_labels",
        )
        p.require(
            isinstance(coefficients, (list, tuple)) and len(coefficients) == len(targets),
            "hierarchical_loss.one_coefficient_per_original_target",
        )
        outer = _fraction(scale, allow_zero=False)
        exact = [
            _fraction(_fraction(value, allow_zero=True) * outer, allow_zero=True)
            for value in coefficients
        ]
        p.require(bool(torch.isfinite(logits).all()), "hierarchical_loss.nonfinite_logits")
        numeric = [float(value) for value in exact]
        p.require(
            all(
                math.isfinite(value) and (raw == 0 or value > 0)
                for raw, value in zip(exact, numeric, strict=True)
            ),
            "hierarchical_loss.scaled_coefficients_representable",
        )
        weights = torch.tensor(numeric, device=logits.device, dtype=torch.float32)
        p.require(
            bool(torch.isfinite(weights).all())
            and all(raw == 0 or weights[index].item() > 0 for index, raw in enumerate(exact)),
            "hierarchical_loss.float32_coefficients_not_underflowed",
        )
        if exact[0] > 0 and all(value == exact[0] for value in exact):
            # Preserve the inherited calculation only after checking its scale
            # in the actual FP32 arithmetic, not merely as a Python float.
            return selected_target_loss(logits, targets, exact[0])
        result = (
            functional.cross_entropy(logits.float(), targets, reduction="none") * weights
        ).sum()
        p.require(bool(torch.isfinite(result.detach())), "hierarchical_loss.finite_loss")
        return result

    def package_loss(self, selected_logits, package, annotation, *, scale=Fraction(1)):
        """Small-model/reference interface; streaming consumers use row_loss."""
        package, annotation = copy.deepcopy((package, annotation))
        coefficients = self.token_coefficients(package, annotation)
        p.require(
            isinstance(selected_logits, (list, tuple))
            and len(selected_logits) == len(coefficients),
            "hierarchical_loss.complete_original_logit_rows",
        )
        values = []
        for logits, original, weights in zip(
            selected_logits, package["rows"], coefficients, strict=True
        ):
            row = validate_row(original)
            labels = [
                label
                for label, selected in zip(row["labels"], row["target_mask"], strict=True)
                if selected
            ]
            values.append(self.row_loss(logits, labels, weights, scale=scale))
        return sum(values)
