"""Numerical controls, not actual financial or Qwen training experiments."""

import copy
from dataclasses import FrozenInstanceError
from fractions import Fraction

import pytest
import torch
import torch.nn.functional as F

from trusted_synthesis.experiments.finance_qa_vnext_hierarchical_loss import protocol as p
from trusted_synthesis.experiments.finance_qa_vnext_hierarchical_loss.loss import (
    HierarchicalTrajectoryLoss,
)
from trusted_synthesis.experiments.finance_qa_vnext_pq_student.loss import selected_target_loss


def package_fixture(
    lengths=(2, 7, 3), layers=("reasoning", "tools", "final"), profile="public_rtf"
):
    from trusted_synthesis.experiments.finance_qa_vnext_hierarchical_loss.representation import (
        build_synthetic_package_annotation,
    )

    rows = []
    for index, count in enumerate(lengths):
        target = [(index + position) % 5 for position in range(count)]
        rows.append(
            {
                "candidate_id": "synthetic_" + str(index),
                "representation": {
                    "input_ids": [1, *target, 0],
                    "labels": [-100, *target, -100],
                    "target_mask": [0, *([1] * count), 0],
                    "sequence_length": count + 2,
                    "target_token_count": count,
                },
            }
        )
    package = {
        "package_id": "synthetic_loss_package",
        "rows": rows,
        "whole_package_target_tokens": sum(lengths),
    }
    return package, build_synthetic_package_annotation(package, list(layers), profile=profile)


def test_policy_is_frozen_and_declares_non_probability_objective():
    loss = HierarchicalTrajectoryLoss()
    value = loss.describe()
    assert value["sum_hierarchical_layer_weights"] == "1"
    assert value["defines_feedback_log_probability"] is False
    with pytest.raises(FrozenInstanceError):
        loss.objective = "tool_only"
    value["fixed_layer_weights"]["reasoning"] = "100"
    assert loss.describe()["fixed_layer_weights"]["reasoning"] == "3/10"


@pytest.mark.parametrize(
    "kwargs", [{"objective": "tool_only"}, {"objective": "111"}, {"profile": "guess_from_text"}]
)
def test_no_unregistered_ablation_or_profile(kwargs):
    with pytest.raises(ValueError):
        HierarchicalTrajectoryLoss(**kwargs)


def test_uniform_row_is_exact_inherited_loss_and_gradient():
    first = torch.tensor([[0.1, 0.4, -0.2], [0.3, -0.4, 0.9]], requires_grad=True)
    second = first.detach().clone().requires_grad_()
    actual = HierarchicalTrajectoryLoss().row_loss(
        first, [1, 2], [Fraction(1, 12)] * 2, scale=Fraction(3, 8)
    )
    expected = selected_target_loss(second, [1, 2], Fraction(1, 32))
    assert torch.equal(actual, expected)
    actual.backward()
    expected.backward()
    assert torch.equal(first.grad, second.grad)


def test_mixed_token_weights_have_no_extra_shift_or_mean():
    logits = torch.tensor([[0.3, 0.7], [-0.1, 0.8], [0.6, 0.2]], requires_grad=True)
    weights = [Fraction(3, 20), Fraction(1, 8), Fraction(0)]
    actual = HierarchicalTrajectoryLoss().row_loss(logits, [1, 0, 1], weights, scale=Fraction(2, 5))
    reference = (
        F.cross_entropy(logits, torch.tensor([1, 0, 1]), reduction="none")
        * torch.tensor([0.06, 0.05, 0.0])
    ).sum()
    assert torch.allclose(actual, reference)
    actual.backward()
    assert torch.equal(logits.grad[-1], torch.zeros(2))
    assert logits.grad[0].abs().sum() > 0


def test_zero_coefficients_keep_connected_zero_gradient():
    logits = torch.randn(2, 4, requires_grad=True)
    result = HierarchicalTrajectoryLoss().row_loss(logits, [1, 2], [0, 0])
    result.backward()
    assert result.item() == 0 and torch.equal(logits.grad, torch.zeros_like(logits))


@pytest.mark.parametrize(
    "coefficients,scale",
    [
        ([Fraction(1, 10**100)] * 2, 1),
        ([Fraction(1, 10**100), Fraction(2, 10**100)], 1),
        ([Fraction(1, 10**20)] * 2, Fraction(1, 10**30)),
        ([10**30] * 2, 10**30),
        ([10**300] * 2, 10**300),
        ([float("nan")] * 2, 1),
        ([-1, 1], 1),
        ([True, 1], 1),
        ([1, 1], 0),
        ([1, 1], False),
        ([1, 1], float("inf")),
    ],
)
def test_uniform_and_nonuniform_scale_fail_closed(coefficients, scale):
    with pytest.raises(ValueError):
        HierarchicalTrajectoryLoss().row_loss(
            torch.zeros(2, 3, requires_grad=True), [0, 1], coefficients, scale=scale
        )


@pytest.mark.parametrize("labels", [[-100, 1], [3, 0], [True, 0], [0.1, 1], [0], [[0, 1]]])
def test_only_actual_selected_integer_labels(labels):
    with pytest.raises(ValueError):
        HierarchicalTrajectoryLoss().row_loss(torch.zeros(2, 3), labels, [1, 1])


@pytest.mark.parametrize("value", [float("nan"), float("inf"), -float("inf")])
def test_even_zero_weight_nonfinite_selected_logits_are_rejected(value):
    logits = torch.zeros(2, 3)
    logits[1, 0] = value
    with pytest.raises(ValueError, match="nonfinite_logits"):
        HierarchicalTrajectoryLoss().row_loss(logits, [0, 1], [1, 0])


def test_package_means_use_layer_totals_not_full_or_row_denominators():
    package, annotation = package_fixture()
    loss = HierarchicalTrajectoryLoss()
    coefficients = loss.token_coefficients(package, annotation)
    assert coefficients == [[Fraction(3, 20)] * 2, [Fraction(1, 14)] * 7, [Fraction(1, 15)] * 3]
    assert sum(map(sum, coefficients)) == 1
    logits = [torch.randn(count, 5, requires_grad=True) for count in (2, 7, 3)]
    actual = loss.package_loss(logits, package, annotation)
    means = [
        F.cross_entropy(
            value, torch.tensor(row["representation"]["labels"][1:-1]), reduction="mean"
        )
        for value, row in zip(logits, package["rows"], strict=True)
    ]
    assert torch.allclose(actual, 0.3 * means[0] + 0.5 * means[1] + 0.2 * means[2])


def test_original_full_is_not_three_unweighted_layer_means():
    package, annotation = package_fixture()
    full = HierarchicalTrajectoryLoss(objective="full_token_mean")
    assert full.token_coefficients(package, annotation) == [
        [Fraction(1, 12)] * count for count in (2, 7, 3)
    ]
    logits = [torch.zeros(count, 5) for count in (2, 7, 3)]
    actual = full.package_loss(logits, package, annotation)
    assert torch.allclose(actual, torch.log(torch.tensor(5.0)))
    assert not torch.allclose(actual, 3 * torch.log(torch.tensor(5.0)))


def test_two_tool_rows_share_the_package_tool_denominator():
    package, annotation = package_fixture((2, 3, 7, 5), ("reasoning", "tools", "tools", "final"))
    actual = HierarchicalTrajectoryLoss().token_coefficients(package, annotation)
    assert actual[1] == [Fraction(1, 20)] * 3 and actual[2] == [Fraction(1, 20)] * 7


def test_missing_reasoning_is_global_TF_profile_not_per_row_renormalization():
    package, annotation = package_fixture((5, 2), ("tools", "final"), "public_tf")
    loss = HierarchicalTrajectoryLoss(profile="public_tf")
    assert loss.token_coefficients(package, annotation) == [
        [Fraction(1, 10)] * 5,
        [Fraction(1, 10)] * 2,
    ]
    assert loss.describe()["sum_hierarchical_layer_weights"] == "7/10"
    with pytest.raises(ValueError, match="common_frozen_profile"):
        HierarchicalTrajectoryLoss().token_coefficients(package, annotation)


@pytest.mark.parametrize("objective", p.OBJECTIVES)
def test_missing_weighted_layer_blocks_both_comparison_conditions(objective):
    with pytest.raises(ValueError):
        package, annotation = package_fixture((2, 3), ("reasoning", "final"))
        HierarchicalTrajectoryLoss(objective=objective).token_coefficients(package, annotation)


def test_original_rows_and_annotation_are_not_mutated():
    package, annotation = package_fixture()
    saved = copy.deepcopy((package, annotation))
    HierarchicalTrajectoryLoss().token_coefficients(package, annotation)
    assert (package, annotation) == saved
