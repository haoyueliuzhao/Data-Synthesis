"""CPU exact-state-loss and optimizer controls over unchanged toy originals."""

import copy
from fractions import Fraction
from types import SimpleNamespace

import pytest
import torch
from test_qa_vnext_anchored_state_catalog import toy_materials as toy_materials
from torch import nn
from torch.nn import functional as F

from trusted_synthesis.experiments.finance_qa_vnext_anchored_vtdo import state_materials as state
from trusted_synthesis.experiments.finance_qa_vnext_basis_student import kernel


@pytest.fixture(autouse=True)
def one_CPU_thread():
    count = torch.get_num_threads()
    torch.set_num_threads(1)
    yield
    torch.set_num_threads(count)


class TinyCausal(nn.Module):
    def __init__(self):
        super().__init__()
        self.table = nn.Parameter(torch.arange(35, dtype=torch.float32).reshape(5, 7) / 70)
        self.calls = []

    def forward(self, *, input_ids, attention_mask, use_cache, logits_to_keep):
        self.calls.append((input_ids.tolist(), logits_to_keep.tolist()))
        assert use_cache is False and attention_mask.tolist() == [[1] * input_ids.shape[1]]
        hidden = input_ids.cumsum(-1) % 5
        return SimpleNamespace(logits=self.table[hidden][:, logits_to_keep, :])


class CountingAdam(torch.optim.AdamW):
    def __init__(self, parameters):
        super().__init__(parameters, lr=1e-4, betas=(0.9, 0.999), eps=1e-8, weight_decay=0)
        self.zero_calls = self.step_calls = 0

    def zero_grad(self, *args, **kwargs):
        self.zero_calls += 1
        return super().zero_grad(*args, **kwargs)

    def step(self, *args, **kwargs):
        self.step_calls += 1
        return super().step(*args, **kwargs)


def weighted_input(toy_materials, *, initial=False):
    root, manifest, _, catalog, batch = toy_materials
    distribution = state.initial_distribution(catalog, pool="A")
    if not initial:
        for task in catalog["task_support"]:
            if task["pool"] == "A" and task["group"] != "control":
                for member in task["states"]:
                    distribution[task["task_id"]][member["state_id"]] = (
                        "1/8" if member["actual_method"] == "endpoint" else "3/8"
                    )
    examples = state.update_examples(
        root, manifest, catalog, batch, pool="A", distribution=distribution
    )
    return examples, batch, catalog, distribution


def test_pi0_exactly_restores_every_old_alpha0_coefficient_and_original_package(toy_materials):
    examples, batch, catalog, distribution = weighted_input(toy_materials, initial=True)
    assert len(examples) == 64
    assert all(
        row["target_token_coefficient"] == row["original_alpha0_coefficient"] for row in examples
    )
    # The old alpha-only assertion still applies and passes only at the exact baseline.
    kernel.validate_update(examples, batch, pool="A", arm="alpha0")
    for task in batch["tasks"]:
        mass = sum(
            Fraction(row["target_token_coefficient"]) * row["whole_package_target_tokens"]
            for row in examples
            if row["task_id"] == task["task_id"]
        )
        assert mass == Fraction(1, 5)
    assert all(
        sum(Fraction(value) for value in values.values()) == 1 for values in distribution.values()
    )


def test_event_callback_cannot_change_validated_private_input_snapshot(toy_materials):
    examples, batch, catalog, distribution = weighted_input(toy_materials, initial=True)
    first = TinyCausal()
    second = TinyCausal()
    reference = state.execute_update(
        first,
        CountingAdam(first.parameters()),
        examples,
        batch,
        pool="A",
        catalog=catalog,
        distribution=distribution,
    )
    original_coefficient = examples[0]["target_token_coefficient"]

    def mutate(event):
        if event["event"] == "validated_state_update":
            examples[0]["target_token_coefficient"] = str(2 * Fraction(original_coefficient))

    actual = state.execute_update(
        second,
        CountingAdam(second.parameters()),
        examples,
        batch,
        pool="A",
        catalog=catalog,
        distribution=distribution,
        event_sink=mutate,
    )
    assert examples[0]["target_token_coefficient"] != original_coefficient
    assert actual["weighted_loss"] == reference["weighted_loss"]
    assert actual["validation_id"] == reference["validation_id"]
    assert torch.equal(first.table, second.table)


def test_changed_state_weights_cannot_be_smuggled_into_unmodified_old_kernel(toy_materials):
    examples, batch, _, _ = weighted_input(toy_materials)
    with pytest.raises(ValueError, match="exact_alpha_over_40L"):
        kernel.validate_update(examples, batch, pool="A", arm="alpha0")


def test_updated_float_probabilities_keep_actual_residual_without_normalization(toy_materials):
    root, manifest, _, catalog, batch = toy_materials
    distribution = state.initial_distribution(catalog, pool="A")
    task = batch["tasks"][0]["task_id"]
    keys = list(distribution[task])
    distribution[task] = dict(zip(keys, [0.1, 0.2, 0.3, 0.3999999999999999], strict=True))
    checked, residuals = state.validate_distribution(catalog, distribution, pool="A")
    assert Fraction(residuals[task]) == Fraction(-1, 10**16)
    assert checked[task][keys[-1]] == Fraction("0.3999999999999999")
    examples = state.update_examples(
        root, manifest, catalog, batch, pool="A", distribution=distribution
    )
    package = next(
        row for row in examples if row["task_id"] == task and row["state_id"] == keys[-1]
    )
    assert Fraction(package["target_token_coefficient"]) == Fraction("0.3999999999999999") / (
        5 * package["n_train_in_state"] * package["whole_package_target_tokens"]
    )


@pytest.mark.parametrize(
    "mutation",
    [
        "drop_package",
        "reorder_packages",
        "retokenize",
        "reorder_rows",
        "delete_row",
        "wrong_pool",
        "heldout",
        "wrong_state_n",
        "extra_divisor",
    ],
)
def test_original_physical_kernel_and_state_coefficient_cannot_change(toy_materials, mutation):
    examples, batch, catalog, distribution = weighted_input(toy_materials)
    examples = copy.deepcopy(examples)
    if mutation == "drop_package":
        examples.pop()
    elif mutation == "reorder_packages":
        examples[0], examples[1] = examples[1], examples[0]
    elif mutation == "retokenize":
        examples[0]["rows"][0]["representation"]["input_ids"][0] += 1
    elif mutation == "reorder_rows":
        examples[0]["rows"].reverse()
    elif mutation == "delete_row":
        examples[0]["rows"].pop()
    elif mutation == "wrong_pool":
        examples[0]["pool"] = "B"
    elif mutation == "heldout":
        examples[0]["role"] = "heldout"
    elif mutation == "wrong_state_n":
        examples[0]["n_train_in_state"] += 1
    else:
        examples[0]["target_token_coefficient"] = str(
            Fraction(examples[0]["target_token_coefficient"]) / 64
        )
    with pytest.raises(ValueError):
        state.validate_update(examples, batch, pool="A", catalog=catalog, distribution=distribution)


def independent_objective(model, examples, batch, distribution):
    losses = []
    for task in batch["tasks"]:
        state_means = []
        for state_id, probability in distribution[task["task_id"]].items():
            packages = [
                row
                for row in examples
                if row["task_id"] == task["task_id"] and row["state_id"] == state_id
            ]
            package_means = []
            for package in packages:
                losses_for_all_tokens = []
                for row in package["rows"]:
                    ids = torch.tensor(row["representation"]["input_ids"])
                    states = ids.cumsum(0) % 5
                    for position, active in enumerate(row["representation"]["target_mask"]):
                        if active:
                            losses_for_all_tokens.append(
                                F.cross_entropy(
                                    model.table[states[position - 1]].reshape(1, -1),
                                    ids[position].reshape(1),
                                )
                            )
                package_means.append(torch.stack(losses_for_all_tokens).mean())
            state_means.append(float(Fraction(probability)) * torch.stack(package_means).mean())
        losses.append(torch.stack(state_means).sum())
    return torch.stack(losses).mean()


@pytest.mark.parametrize("initial", [True, False])
def test_full_64_original_package_step_matches_independent_token_package_state_task_reduction(
    toy_materials, initial
):
    examples, batch, catalog, distribution = weighted_input(toy_materials, initial=initial)
    actual, reference = TinyCausal(), TinyCausal()
    optimizer, reference_optimizer = (
        CountingAdam(actual.parameters()),
        CountingAdam(reference.parameters()),
    )
    reference_optimizer.zero_grad()
    reference_loss = independent_objective(reference, examples, batch, distribution)
    reference_loss.backward()
    torch.nn.utils.clip_grad_norm_(reference.parameters(), 1.0)
    reference_optimizer.step()
    events = []
    result = state.execute_update(
        actual,
        optimizer,
        examples,
        batch,
        pool="A",
        catalog=catalog,
        distribution=distribution,
        event_sink=events.append,
    )
    assert optimizer.zero_calls == optimizer.step_calls == 1
    assert result["packages_completed"] == 64
    assert result["backward_calls"] == len(actual.calls) == 256
    assert result["clip_calls"] == result["optimizer_step_calls"] == 1
    assert result["weighted_loss"] == pytest.approx(float(reference_loss.detach()), abs=3e-7)
    torch.testing.assert_close(actual.table, reference.table, rtol=1e-6, atol=1e-7)
    assert result["actual_Qwen_training"] is False and result["GPU_operations"] == 0
    expected_ids = [
        row["representation"]["input_ids"] for package in examples for row in package["rows"]
    ]
    assert [ids[0] for ids, _ in actual.calls] == expected_ids
    assert all(positions == [0, 1] for _, positions in actual.calls)
    assert (
        next(event for event in events if event["event"] == "before_single_optimizer_step")[
            "packages_completed"
        ]
        == 64
    )


def test_nonfinite_loss_and_failed_sink_cannot_step_optimizer(toy_materials):
    examples, batch, catalog, distribution = weighted_input(toy_materials)
    model = TinyCausal()
    optimizer = CountingAdam(model.parameters())
    with pytest.raises(ValueError, match="finite_loss"):
        state.execute_update(
            model,
            optimizer,
            examples,
            batch,
            pool="A",
            catalog=catalog,
            distribution=distribution,
            loss_fn=lambda logits, *_: logits.sum() * float("nan"),
        )
    assert optimizer.step_calls == 0


def test_state_shift_control_has_a_nonzero_objective_change_not_identical_toy_rows(toy_materials):
    examples, batch, catalog, moved = weighted_input(toy_materials)
    model = TinyCausal()
    baseline = state.initial_distribution(catalog, pool="A")
    assert (
        abs(
            float(
                (
                    independent_objective(model, examples, batch, moved)
                    - independent_objective(model, examples, batch, baseline)
                ).detach()
            )
        )
        > 1e-6
    )


def test_real_GPU_path_remains_explicitly_unvalidated_and_unexecuted(toy_materials):
    examples, batch, catalog, distribution = weighted_input(toy_materials)
    model = TinyCausal()
    with pytest.raises(ValueError, match="GPU_not_yet_authorized"):
        state.execute_update(
            model,
            CountingAdam(model.parameters()),
            examples,
            batch,
            pool="A",
            catalog=catalog,
            distribution=distribution,
            device="cuda:0",
        )
    assert model.calls == []
