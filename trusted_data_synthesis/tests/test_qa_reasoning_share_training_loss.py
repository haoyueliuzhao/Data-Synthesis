"""Actual finite-pool weights and CPU loss assembly; no Student execution."""

from __future__ import annotations

import copy
import io
import zipfile
from collections.abc import Iterator
from fractions import Fraction
from pathlib import Path
from typing import Any

import numpy as np
import pytest
import torch

from trusted_synthesis.experiments.qa_reasoning_share_training_preflight import (
    inputs,
    loss,
    models,
    tokenization,
    weights,
)

ROOT = Path(__file__).resolve().parents[2]
TARGET_TOTALS = {"M02": 2_812, "M03": 4_691, "M04": 2_793, "M05": 2_817, "M06": 2_826}


@pytest.fixture(scope="module")
def actual() -> Iterator[dict[str, Any]]:
    def forbidden(*args: Any, **kwargs: Any) -> None:
        raise AssertionError(
            "this test may tokenize and aggregate CPU arrays, never train a Student"
        )

    with pytest.MonkeyPatch.context() as guard:
        guard.setattr(torch.cuda, "_lazy_init", forbidden)
        guard.setattr(torch.Tensor, "backward", forbidden)
        from transformers import AutoModelForCausalLM

        guard.setattr(AutoModelForCausalLM, "from_pretrained", forbidden)
        frozen = inputs.load_inputs(ROOT)
        binding = tokenization.register_tokenizer(ROOT)
        contract = models.representation_contract(binding)
        dataset = inputs.export_rows(frozen, contract)
        original_dataset = copy.deepcopy(dataset)
        encoded = models.record(
            "tokenized_dataset",
            dataset_id=dataset["id"],
            representation_contract_id=contract["id"],
            tokenizer_binding_id=binding["id"],
            rows=tokenization.tokenize_rows(dataset["rows"], binding),
        )
        kernel = weights.build_kernel(frozen, dataset, encoded)
        batch, arrays, binary = loss.collate(encoded, binding["pad_token_id"])
        arrays_before = {name: value.copy() for name, value in arrays.items()}
        views = weights.build_views(frozen, dataset, encoded, kernel, batch)
        checks, bundles = loss.run_loss_checks(dataset, encoded, kernel, batch, arrays, views)
        yield {
            "inputs": frozen,
            "binding": binding,
            "contract": contract,
            "dataset": dataset,
            "tokens": encoded,
            "kernel": kernel,
            "batch": batch,
            "arrays": arrays,
            "binary": binary,
            "views": views,
            "checks": checks,
            "bundles": bundles,
        }
        assert dataset == original_dataset
        for name, value in arrays.items():
            np.testing.assert_array_equal(value, arrays_before[name])
        assert torch.cuda.is_initialized() is False
        inputs.assert_unchanged(ROOT, frozen)


def _fraction(value: dict[str, Any]) -> Fraction:
    """Independent arithmetic interpretation, not the source ratio helper."""
    result = Fraction(value["numerator"], value["denominator"])
    assert value["exact"] == f"{result.numerator}/{result.denominator}"
    return result


def test_real_kernel_preserves_closed_support_and_uniform_original_trajectory_selection(
    actual: dict[str, Any],
) -> None:
    kernel = actual["kernel"]
    trajectories = kernel["trajectories"]
    assert [item["session_label"] for item in trajectories] == list(TARGET_TOTALS)
    assert {
        item["session_label"]: item["target_token_count"] for item in trajectories
    } == TARGET_TOTALS
    assert [item["row_count"] for item in trajectories] == [5, 7, 5, 5, 5]
    assert len({item["session_id"] for item in trajectories}) == 5
    assert len({item["state_id"] for item in trajectories}) == 2
    for item in trajectories:
        expected = Fraction(1) if item["session_label"] == "M03" else Fraction(1, 4)
        assert _fraction(item["within_state_probability"]) == expected
    assert kernel["original_partition_id"] == actual["inputs"]["partition"]["id"]
    assert kernel["independently_observed_trajectories"] == 5
    assert kernel["new_trajectories"] == 0
    assert kernel["fresh_generation_kernel"] is False
    assert kernel["resampling_copies_count_as_new_samples"] is False


def test_P_and_Q_exact_trajectory_and_class_mass_use_actual_content_token_denominators(
    actual: dict[str, Any],
) -> None:
    trajectories = {item["session_id"]: item for item in actual["kernel"]["trajectories"]}
    token_by_row = {row["row_id"]: row for row in actual["tokens"]["rows"]}
    for view in actual["views"]:
        expected_by_state: dict[str, Fraction] = {}
        actual_by_state: dict[str, Fraction] = {}
        for item in view["trajectory_weights"]:
            source = trajectories[item["session_id"]]
            is_b = source["session_label"] == "M03"
            probability = (
                Fraction(1, 5)
                if view["name"] == "P"
                else Fraction(1, 2)
                if is_b
                else Fraction(1, 8)
            )
            assert _fraction(item["probability"]) == probability
            assert (
                _fraction(item["token_coefficient"]) == probability / source["target_token_count"]
            )
            expected_by_state[item["state_id"]] = (
                (Fraction(1, 5) if is_b else Fraction(4, 5))
                if view["name"] == "P"
                else Fraction(1, 2)
            )
        for row in view["row_weights"]:
            source = token_by_row[row["row_id"]]
            assert sum(source["target_mask"]) == source["target_token_count"]
            mass = _fraction(row["token_coefficient"]) * sum(source["target_mask"])
            state = row["state_id"]
            actual_by_state[state] = actual_by_state.get(state, Fraction(0)) + mass
        assert actual_by_state == expected_by_state
        assert sum(actual_by_state.values()) == 1
        assert {
            item["state_id"]: _fraction(item["probability"]) for item in view["pi"]
        } == expected_by_state


def test_two_views_share_every_base_object_and_only_change_class_probability_coefficients(
    actual: dict[str, Any],
) -> None:
    p, q = actual["views"]
    assert (p["name"], q["name"]) == ("P", "Q")
    for key in (
        "kernel_id",
        "dataset_id",
        "tokenized_dataset_id",
        "tokenizer_binding_id",
        "representation_contract_id",
        "base_batch_id",
        "row_ids",
    ):
        assert p[key] == q[key]
    for left, right in zip(p["row_weights"], q["row_weights"], strict=True):
        assert {key: value for key, value in left.items() if key != "token_coefficient"} == {
            key: value for key, value in right.items() if key != "token_coefficient"
        }
    assert p["normalization_after_weighted_sum"] is q["normalization_after_weighted_sum"] is False
    assert p["only_class_mass_intervention"] is q["only_class_mass_intervention"] is True
    assert p["training_release"] is q["training_release"] is False
    assert p["base_batch_id"] == actual["batch"]["id"]


def test_naive_row_and_global_token_means_are_detectably_different_objectives(
    actual: dict[str, Any],
) -> None:
    summary = weights.mass_summary(actual["kernel"], actual["views"])
    b_state = next(
        item["state_id"]
        for item in actual["kernel"]["trajectories"]
        if item["session_label"] == "M03"
    )
    b = next(item for item in summary["naive_normalizations"] if item["state_id"] == b_state)
    assert summary["row_total"] == 27
    assert summary["target_token_total"] == 15_939
    assert _fraction(b["equal_row_implicit_mass"]) == Fraction(7, 27)
    assert _fraction(b["global_target_token_mean_implicit_mass"]) == Fraction(4_691, 15_939)
    assert Fraction(7, 27) != Fraction(4_691, 15_939) != Fraction(1, 5)
    assert actual["inputs"]["empirical_measurement"]["q"]["exact"] == "5/6"


def test_real_cpu_collation_right_padding_masks_and_causal_weight_alignment(
    actual: dict[str, Any],
) -> None:
    batch, arrays = actual["batch"], actual["arrays"]
    assert batch["shape"] == [27, 15_110]
    assert batch["real_token_count"] == 368_869
    assert batch["target_token_count"] == 15_939
    assert batch["padding_token_count"] == 39_101
    assert batch["array_dtypes"] == {
        "input_ids": "int64",
        "labels": "int64",
        "attention_mask": "int8",
        "target_mask": "int8",
    }
    for index, row in enumerate(actual["tokens"]["rows"]):
        count = row["sequence_length"]
        for name in arrays:
            np.testing.assert_array_equal(arrays[name][index, :count], row[name])
        assert np.all(arrays["input_ids"][index, count:] == 151643)
        assert np.all(arrays["labels"][index, count:] == -100)
        assert np.all(arrays["attention_mask"][index, count:] == 0)
        assert np.all(arrays["target_mask"][index, count:] == 0)
    for view in actual["views"]:
        coefficients = loss.coefficient_array(view, arrays)
        assert coefficients.shape == (27, 15_109)
        assert coefficients.dtype == np.float64
        mask = arrays["target_mask"][:, 1:].astype(bool)
        assert np.all(coefficients[~mask] == 0)
        assert np.all(coefficients[mask] > 0)
        assert float(coefficients.sum()) == pytest.approx(1.0, rel=0, abs=1e-12)
        for index, row in enumerate(view["row_weights"]):
            assert np.all(
                coefficients[index, mask[index]] == float(_fraction(row["token_coefficient"]))
            )


def test_npz_is_deterministic_roundtrippable_and_uses_fixed_zip_metadata(
    actual: dict[str, Any],
) -> None:
    arrays = actual["arrays"]
    binary = actual["binary"]
    assert loss.encode_arrays(arrays) == binary
    assert loss.encode_arrays(dict(reversed(list(arrays.items())))) == binary
    decoded = loss.decode_arrays(binary)
    assert set(decoded) == set(arrays)
    for name in arrays:
        assert decoded[name].dtype == arrays[name].dtype
        np.testing.assert_array_equal(decoded[name], arrays[name])
    with zipfile.ZipFile(io.BytesIO(binary)) as archive:
        assert archive.namelist() == [name + ".npy" for name in sorted(arrays)]
        for item in archive.infolist():
            assert item.date_time == (1980, 1, 1, 0, 0, 0)
            assert item.compress_type == zipfile.ZIP_DEFLATED
            assert item.external_attr >> 16 == 0o600
    assert actual["batch"]["npz_sha256"] == models.sha(binary)
    assert actual["batch"]["npz_byte_count"] == len(binary)


def test_all_18_controlled_losses_and_microbatch_sums_match_exact_fraction_objective(
    actual: dict[str, Any],
) -> None:
    report = actual["checks"]
    assert report["check_count"] == len(report["checks"]) == 18
    assert report["passed"] is True
    for check in report["checks"]:
        expected = float(_fraction(check["expected"]))
        assert check["actual_float64"] == pytest.approx(expected, rel=0, abs=1e-12)
        assert check["fixed_coefficient_microbatch_sum"] == pytest.approx(
            expected, rel=0, abs=1e-12
        )
        assert check["absolute_error"] <= 1e-12 and check["microbatch_absolute_error"] <= 1e-12
        assert check["passed"] is True
        if check["scenario"] == "all_one":
            assert expected == 1.0
    assert report["causal_shift"] == 1
    assert report["masked_nlls_are_nan_and_ignored"] is True
    assert report["Student_model_loaded"] is False
    for field in ("Student_forward_passes", "backward_calls", "optimizer_steps", "GPU_jobs"):
        assert report[field] == 0
    assert report["CUDA_initialized"] is False
    assert report["controlled_losses_are_not_Student_losses"] is True
    assert report["utility_or_Contribution_measured"] is False


def test_loss_control_and_two_weight_bundles_rebuild_from_same_base_without_mutation(
    actual: dict[str, Any],
) -> None:
    second, bundles = loss.run_loss_checks(
        actual["dataset"],
        actual["tokens"],
        actual["kernel"],
        actual["batch"],
        actual["arrays"],
        actual["views"],
    )
    assert second == actual["checks"]
    assert bundles == actual["bundles"]
    assert bundles["P"] != bundles["Q"]
    for view in actual["views"]:
        decoded = loss.decode_arrays(bundles[view["name"]])
        assert set(decoded) == {"causal_token_coefficients"}
        np.testing.assert_array_equal(
            decoded["causal_token_coefficients"], loss.coefficient_array(view, actual["arrays"])
        )
    assert loss.encode_arrays(actual["arrays"]) == actual["binary"]


@pytest.mark.parametrize("mutation", ["missing_tokens", "mixed_state", "zero_targets"])
def test_kernel_rejects_incomplete_or_inconsistent_trajectory_materialization(
    actual: dict[str, Any], mutation: str
) -> None:
    dataset, encoded = copy.deepcopy(actual["dataset"]), copy.deepcopy(actual["tokens"])
    if mutation == "missing_tokens":
        encoded["rows"].pop()
        code = "weights.token_row_totality"
    elif mutation == "mixed_state":
        other = next(row["state_id"] for row in dataset["rows"] if row["session_label"] == "M03")
        dataset["rows"][1]["state_id"] = other
        code = "weights.trajectory_state"
    else:
        selected = {row["id"] for row in dataset["rows"] if row["session_label"] == "M03"}
        for row in encoded["rows"]:
            if row["row_id"] in selected:
                row["target_token_count"] = 0
        code = "weights.empty_trajectory"
    with pytest.raises(models.TrainingPreflightError, match=code):
        weights.build_kernel(actual["inputs"], dataset, encoded)


@pytest.mark.parametrize("mutation", ["support", "mass"])
def test_weight_view_rejects_changed_empirical_support_or_total(
    actual: dict[str, Any], mutation: str
) -> None:
    frozen = copy.deepcopy(actual["inputs"])
    item = frozen["empirical_measurement"]["conditional_distribution"][0]
    if mutation == "support":
        item["state_id"] = "unregistered-state"
        code = "weights.measured_support"
    else:
        item["conditional"]["numerator"] += 1
        code = "weights.class_total"
    with pytest.raises(models.TrainingPreflightError, match=code):
        weights.build_views(
            frozen, actual["dataset"], actual["tokens"], actual["kernel"], actual["batch"]
        )


def test_collator_and_coefficient_builder_reject_incomplete_rows(actual: dict[str, Any]) -> None:
    encoded = copy.deepcopy(actual["tokens"])
    encoded["rows"][0]["labels"].pop()
    with pytest.raises(models.TrainingPreflightError, match="loss.row_array_length"):
        loss.collate(encoded, 151643)
    view = copy.deepcopy(actual["views"][0])
    view["row_weights"].pop()
    with pytest.raises(models.TrainingPreflightError, match="loss.weight_row_count"):
        loss.coefficient_array(view, actual["arrays"])


def _toy() -> tuple[torch.Tensor, torch.Tensor, torch.Tensor]:
    labels = torch.tensor([[-100, 7, 8, -100], [-100, 9, -100, -100]], dtype=torch.int64)
    nll = torch.tensor(
        [[2.0, 4.0, float("nan")], [6.0, float("nan"), float("inf")]], dtype=torch.float64
    )
    coefficients = torch.tensor([[0.1, 0.2, 0.0], [0.3, 0.0, 0.0]], dtype=torch.float64)
    return nll, labels, coefficients


def test_aggregate_uses_shift_one_and_fixed_sum_without_secondary_normalization() -> None:
    nll, labels, coefficients = _toy()
    result = loss.aggregate_loss(nll, labels, coefficients)
    expected = 2 * 0.1 + 4 * 0.2 + 6 * 0.3
    assert float(result) == pytest.approx(expected, rel=0, abs=1e-15)
    assert float(result) != pytest.approx(expected / float(coefficients.sum()))
    assert float(result) != pytest.approx(expected / 3)
    chunks = sum(
        float(loss.aggregate_loss(nll[i : i + 1], labels[i : i + 1], coefficients[i : i + 1]))
        for i in range(2)
    )
    assert chunks == pytest.approx(expected, rel=0, abs=1e-15)
    assert result.device.type == "cpu" and result.dtype == torch.float64


def test_inactive_nan_infinity_and_negative_nll_are_ignored_with_zero_weight() -> None:
    nll, labels, coefficients = _toy()
    nll[labels[:, 1:] == -100] = torch.tensor(
        [float("nan"), float("-inf"), -99.0], dtype=torch.float64
    )
    assert float(loss.aggregate_loss(nll, labels, coefficients)) == pytest.approx(
        2.8, rel=0, abs=1e-15
    )


@pytest.mark.parametrize("value", [float("nan"), float("inf"), float("-inf"), -0.01])
def test_nonfinite_or_negative_active_nll_is_rejected(value: float) -> None:
    nll, labels, coefficients = _toy()
    nll[0, 0] = value
    with pytest.raises(models.TrainingPreflightError, match="loss.invalid_active_nll"):
        loss.aggregate_loss(nll, labels, coefficients)


@pytest.mark.parametrize("value", [float("nan"), float("inf"), -0.01])
def test_nonfinite_or_negative_active_coefficient_is_rejected(value: float) -> None:
    nll, labels, coefficients = _toy()
    coefficients[0, 0] = value
    with pytest.raises(models.TrainingPreflightError, match="loss.invalid_coefficient"):
        loss.aggregate_loss(nll, labels, coefficients)


def test_any_non_target_coefficient_is_rejected() -> None:
    nll, labels, coefficients = _toy()
    coefficients[0, 2] = 0.1
    with pytest.raises(models.TrainingPreflightError, match="loss.non_target_weight"):
        loss.aggregate_loss(nll, labels, coefficients)


@pytest.mark.parametrize(
    "mutation", ["nll_length", "label_length", "label_rank", "coefficient_rank"]
)
def test_causal_shape_and_rank_mismatches_are_explicitly_rejected(mutation: str) -> None:
    nll, labels, coefficients = _toy()
    if mutation == "nll_length":
        nll = nll[:, :-1]
    elif mutation == "label_length":
        labels = labels[:, :-1]
    elif mutation == "label_rank":
        labels = labels[0]
    else:
        coefficients = coefficients[:, :, None]
    code = "loss.causal_rank" if mutation.endswith("rank") else "loss.causal_shapes"
    with pytest.raises(models.TrainingPreflightError, match=code):
        loss.aggregate_loss(nll, labels, coefficients)


@pytest.mark.parametrize("which", [0, 1, 2])
def test_non_cpu_tensor_is_rejected_without_creating_a_cuda_tensor(which: int) -> None:
    values = list(_toy())
    values[which] = values[which].to(device="meta")
    with pytest.raises(models.TrainingPreflightError, match="loss.cpu_only"):
        loss.aggregate_loss(*values)


def test_empty_fixed_microbatch_has_zero_contribution() -> None:
    nll, labels, coefficients = _toy()
    assert float(loss.aggregate_loss(nll[:0], labels[:0], coefficients[:0])) == 0.0
