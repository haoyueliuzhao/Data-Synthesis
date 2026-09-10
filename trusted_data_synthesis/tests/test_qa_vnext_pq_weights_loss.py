"""New P/Q exact-weight and CPU-loss controls; no old tokenization or Student load."""

import copy
from fractions import Fraction
from pathlib import Path
from unittest.mock import patch

import pytest
import torch
import torch.nn.functional as functional

from trusted_synthesis.experiments.finance_qa_vnext_pq_student import loss, weights
from trusted_synthesis.experiments.finance_qa_vnext_pq_student.plan import record
from trusted_synthesis.experiments.finance_qa_vnext_task_panel.guards import execution_guard
from trusted_synthesis.experiments.qa_reasoning_share_training_preflight import tokenization

ROOT = Path(__file__).resolve().parents[2]


@pytest.fixture(scope="module", autouse=True)
def cpu_no_model_or_tokenizer():
    with (
        execution_guard(online=False) as counts,
        patch.object(
            tokenization,
            "load_tokenizer",
            side_effect=AssertionError("no retokenization authorized"),
        ),
    ):
        yield
        assert not any(counts.values())
        assert not torch.cuda.is_initialized()


@pytest.fixture(scope="module")
def view():
    return weights.build(ROOT)


@pytest.fixture(scope="module")
def rows(view):
    return weights.load_rows(ROOT, view)


def reidentify(value):
    return record(
        "pq_weight_views",
        **{key: item for key, item in value.items() if key not in {"id", "schema_version"}},
    )


def probes(view):
    return {
        row["row_index"]: [
            Fraction(row["row_index"] + 1, 13) + Fraction(position + 1, 997)
            for position in range(row["target_token_count"])
        ]
        for row in view["rows"]
    }


def test_exact_task_class_kernel_and_package_masses_match_the_audit(view):
    check = weights.validate_weights(view)
    assert check["total_mass_P"] == check["total_mass_Q"] == "1"
    assert check["changed_package_labels"] == ["T_L1_01", "T_L1_03", "T_L1_04"]
    for arm in weights.ARMS:
        assert set(view["views"][arm]["task_masses"].values()) == {"1/6"}
    assert view["views"]["P"]["conditional_class_probabilities"]["L1"] == {
        weights.BALANCE_CLASS: "2/3",
        weights.MOVEMENT_CLASS: "1/3",
    }
    assert set(view["views"]["Q"]["conditional_class_probabilities"]["L1"].values()) == {"1/2"}
    by_label = {package["session_label"]: package for package in view["packages"]}
    for label in weights.BALANCE_LABELS:
        assert by_label[label]["kappa"] == "1/2"
        assert by_label[label]["mass"] == {"P": "1/18", "Q": "1/24"}
    assert by_label[weights.MOVEMENT_LABEL]["kappa"] == "1"
    assert by_label[weights.MOVEMENT_LABEL]["mass"] == {"P": "1/18", "Q": "1/12"}
    assert [
        by_label[label]["target_token_count"] for label in ("T_L1_01", "T_L1_03", "T_L1_04")
    ] == [259, 366, 315]
    for package in view["packages"]:
        for row_index in package["row_indices"]:
            row = view["rows"][row_index]
            for arm in weights.ARMS:
                assert Fraction(row["coefficient"][arm]) * package[
                    "target_token_count"
                ] == Fraction(package["mass"][arm])


def test_original_36_rows_are_loaded_unchanged_with_one_causal_selection(view, rows):
    assert len(rows) == 36
    assert sum(len(row["target_ids"]) for row in rows) == 4793
    assert sum(row["sequence_length"] for row in rows) == 232603
    for row in rows:
        for name in weights.ARRAYS:
            assert row[name] == row["token_record"][name]
        positions = row["target_positions"]
        assert row["logit_positions"] == [index - 1 for index in positions]
        assert row["target_ids"] == [row["labels"][index] for index in positions]
        assert all(row["labels"][index] == -100 for index in range(positions[0]))
        assert row["labels"][-2:] == [-100, -100]
        assert row["candidate"]["id"] == row["candidate_reference"]["id"]
        assert row["token_record"]["id"] == row["token_reference"]["id"]
        assert row["coefficient"] == view["rows"][row["row_index"]]["coefficient"]


def test_actual_target_count_probes_obey_exact_delta_and_arbitrary_row_blocks(view):
    values = probes(view)
    package_losses = loss.package_mean_losses(view, values)
    p = loss.simulated_objective(view, values, "P")
    q = loss.simulated_objective(view, values, "Q")
    expected = (
        package_losses["T_L1_03"] - (package_losses["T_L1_01"] + package_losses["T_L1_04"]) / 2
    ) / 36
    assert q - p == expected
    for arm, objective in (("P", p), ("Q", q)):
        grouped = sum(
            Fraction(package["mass"][arm]) * package_losses[package["session_label"]]
            for package in view["packages"]
        )
        assert grouped == objective
        for blocks in (
            [list(range(i, 36, 5)) for i in range(5)],
            [list(range(36))],
            [[i] for i in range(36)],
        ):
            assert (
                sum(
                    loss.simulated_objective(view, values, arm, row_indices=block)
                    for block in blocks
                )
                == objective
            )


def test_unit_nll_has_unit_mass_not_a_row_or_global_token_mean(view):
    unit = {row["row_index"]: [1] * row["target_token_count"] for row in view["rows"]}
    assert loss.simulated_objective(view, unit, "P") == 1
    assert loss.simulated_objective(view, unit, "Q") == 1
    values = probes(view)
    correct = loss.simulated_objective(view, values, "P")
    global_mean = sum(sum(items) for items in values.values()) / 4793
    row_mean = sum(sum(items) / len(items) for items in values.values()) / 36
    assert correct != global_mean and correct != row_mean


@pytest.mark.parametrize("mutation", ["row_average", "nonL1_Q_change", "class_kernel"])
def test_rehashed_invalid_weight_interventions_are_rejected(view, mutation):
    changed = copy.deepcopy(view)
    if mutation == "row_average":
        row = changed["rows"][0]
        mass = changed["views"]["P"]["package_masses"][row["session_label"]]
        row["coefficient"]["P"] = str(Fraction(mass) / row["target_token_count"])
        expected = "weights.whole_package_target_token_mean"
    elif mutation == "nonL1_Q_change":
        changed["rows"][0]["coefficient"]["Q"] = "1/4793"
        expected = "weights.whole_package_target_token_mean"
    else:
        changed["packages"][0]["kappa"] = "1/2"
        expected = "weights.fixed_class_internal_kernel_and_package_length"
    with pytest.raises(ValueError, match=expected):
        weights.validate_weights(reidentify(changed))


def test_changed_source_reference_and_mask_cannot_reach_training(view, monkeypatch):
    changed = copy.deepcopy(view)
    changed["source_references"]["index"]["sha256"] = "0" * 64
    with pytest.raises(ValueError, match="weights.bound_reference_changed"):
        weights.load_rows(ROOT, reidentify(changed))
    original_bound = weights._bound

    def altered_mask(root, reference, **kwargs):
        value = original_bound(root, reference, **kwargs)
        if reference["path"].endswith(".tokens.json"):
            value["labels"][1] = value["input_ids"][1]
            value["target_mask"][1] = 1
        return value

    monkeypatch.setattr(weights, "_bound", altered_mask)
    with pytest.raises(ValueError, match="weights.original_target_only_labels"):
        weights.load_rows(ROOT, view)


def test_selected_logits_equal_full_causal_ce_and_gradient():
    generator = torch.Generator(device="cpu").manual_seed(113)
    original = torch.randn(1, 11, 17, generator=generator, requires_grad=True)
    selected = original.detach().clone().requires_grad_()
    labels = torch.tensor([[-100, -100, -100, -100, 3, 7, 4, 9, -100, -100, -100]])
    coefficient = Fraction(1, 36 * 7)
    expected = functional.cross_entropy(
        original[:, :-1].float().reshape(-1, 17),
        labels[:, 1:].reshape(-1),
        ignore_index=-100,
        reduction="sum",
    ) * float(coefficient)
    positions = torch.where(labels[0] != -100)[0]
    actual = loss.selected_target_loss(
        selected[:, positions - 1], labels[0, positions], coefficient
    )
    assert actual.dtype == torch.float32
    torch.testing.assert_close(actual, expected, atol=1e-7, rtol=1e-6)
    actual_gradient = torch.autograd.grad(actual, selected)[0]
    expected_gradient = torch.autograd.grad(expected, original)[0]
    torch.testing.assert_close(actual_gradient, expected_gradient, atol=1e-8, rtol=1e-6)
    assert torch.count_nonzero(actual_gradient[:, :3]) == 0
    torch.testing.assert_close(loss.full_causal_loss(selected, labels, coefficient), actual)


def test_selected_target_chunks_add_without_microbatch_mean_or_gradient_change():
    generator = torch.Generator(device="cpu").manual_seed(29)
    one = torch.randn(13, 19, generator=generator, requires_grad=True)
    blocks = one.detach().clone().requires_grad_()
    targets = torch.arange(13, dtype=torch.long)
    coefficient = Fraction(1, 18 * 366)
    whole = loss.selected_target_loss(one, targets, coefficient)
    split = sum(
        loss.selected_target_loss(blocks[left:right], targets[left:right], coefficient)
        for left, right in ((0, 2), (2, 7), (7, 13))
    )
    torch.testing.assert_close(split, whole, atol=1e-7, rtol=1e-6)
    torch.testing.assert_close(
        torch.autograd.grad(split, blocks)[0],
        torch.autograd.grad(whole, one)[0],
        atol=1e-8,
        rtol=1e-6,
    )


def test_prompt_suffix_nan_is_not_an_active_loss_and_bfloat16_logits_use_float32_ce():
    logits = torch.full((8, 7), float("nan"))
    logits[3:5] = torch.zeros((2, 7))
    labels = [-100, -100, -100, -100, 2, 4, -100, -100]
    actual = loss.full_causal_loss(logits, labels, "1/10")
    assert torch.isfinite(actual)
    bfloat = torch.zeros((2, 7), dtype=torch.bfloat16, requires_grad=True)
    reduced = loss.selected_target_loss(bfloat, [2, 4], "1/10")
    assert reduced.dtype == torch.float32
    assert torch.autograd.grad(reduced, bfloat)[0].dtype == torch.bfloat16
    torch.testing.assert_close(actual, reduced)
    logits[3, 0] = float("nan")
    with pytest.raises(ValueError, match="loss.nonfinite_active_logits"):
        loss.full_causal_loss(logits, labels, "1/10")


@pytest.mark.parametrize("coefficient", [0, -1, "nan", float("inf"), True])
def test_invalid_fixed_coefficient_rejected(coefficient):
    with pytest.raises(ValueError, match=r"loss\."):
        loss.selected_target_loss(torch.zeros(2, 7), [2, 4], coefficient)


def test_ignored_or_misaligned_selected_targets_are_rejected():
    for targets in ([-100, 4], [2], [2, 7], [2.2, 4.0]):
        with pytest.raises(ValueError, match=r"loss\."):
            loss.selected_target_loss(torch.zeros(2, 7), targets, "1/10")
    with pytest.raises(ValueError, match="loss.full_label_shape_and_first_position"):
        loss.full_causal_loss(torch.zeros(4, 7), [1, -100, 2, -100], "1/10")
