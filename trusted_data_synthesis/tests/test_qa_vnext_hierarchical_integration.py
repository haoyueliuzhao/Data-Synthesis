"""Synthetic CPU loss/gradient/AdamW controls; no real materials or Student."""

import copy
from fractions import Fraction
from types import SimpleNamespace

import pytest
import torch
import torch.nn.functional as F
from test_qa_vnext_anchored_state_catalog import toy_materials as toy_materials

from trusted_synthesis.experiments.finance_qa_vnext_anchored_vtdo import (
    gradients as original_gradients,
)
from trusted_synthesis.experiments.finance_qa_vnext_anchored_vtdo import state_materials as original
from trusted_synthesis.experiments.finance_qa_vnext_hierarchical_loss import integration as live
from trusted_synthesis.experiments.finance_qa_vnext_hierarchical_loss import protocol as p
from trusted_synthesis.experiments.finance_qa_vnext_hierarchical_loss.loss import (
    HierarchicalTrajectoryLoss,
)
from trusted_synthesis.experiments.finance_qa_vnext_hierarchical_loss.representation import (
    build_synthetic_package_annotation,
)


@pytest.fixture(autouse=True)
def one_thread():
    old = torch.get_num_threads()
    torch.set_num_threads(1)
    yield
    torch.set_num_threads(old)


class Tiny(torch.nn.Module):
    def __init__(self):
        super().__init__()
        self.table = torch.nn.Parameter(torch.arange(35, dtype=torch.float32).reshape(5, 7) / 31)
        self.register_buffer("scale", torch.tensor(1.0))
        self.dropout = torch.nn.Dropout(0.0)
        self.calls = []
        self.mutate_buffer = False
        self.nonfinite = False

    def forward(self, *, input_ids, attention_mask, use_cache, logits_to_keep):
        assert use_cache is False
        assert attention_mask.tolist() == [[1] * input_ids.shape[1]]
        self.calls.append((input_ids.tolist(), logits_to_keep.tolist(), self.training))
        if self.mutate_buffer:
            self.scale.add_(0.1)
        hidden = input_ids.cumsum(-1) % 5
        logits = self.dropout(self.table[hidden]) * self.scale
        if self.nonfinite:
            logits = logits * float("nan")
        return SimpleNamespace(logits=logits[:, logits_to_keep, :])


class CountingAdam(torch.optim.AdamW):
    def __init__(self, model):
        super().__init__(model.parameters(), lr=0.002, eps=0.03, weight_decay=0.02)
        self.zero_calls = self.step_calls = 0

    def zero_grad(self, *args, **kwargs):
        self.zero_calls += 1
        return super().zero_grad(*args, **kwargs)

    def step(self, *args, **kwargs):
        self.step_calls += 1
        return super().step(*args, **kwargs)


def inputs(toy_materials, profile="public_rtf", *, initial=True):
    root, manifest, _, catalog, batch = toy_materials
    manifest, catalog, batch = copy.deepcopy((manifest, catalog, batch))
    pi = original.initial_distribution(catalog, pool="A")
    if not initial:
        for row in catalog["task_support"]:
            if row["pool"] == "A" and row["group"] != "control":
                for state in row["states"]:
                    pi[row["task_id"]][state["state_id"]] = (
                        "1/8" if state["actual_method"] == "endpoint" else "3/8"
                    )
    examples = original.update_examples(root, manifest, catalog, batch, pool="A", distribution=pi)
    row_layers = (
        ["reasoning", "tools", "tools", "final"]
        if profile == "public_rtf"
        else ["tools", "tools", "tools", "final"]
    )
    annotations = {
        row["package_id"]: build_synthetic_package_annotation(row, row_layers, profile=profile)
        for row in examples
    }
    return examples, batch, catalog, pi, annotations


def step(model, optimizer, data, loss, **kwargs):
    examples, batch, catalog, pi, annotations = data
    return live.execute_update_cpu(
        model,
        optimizer,
        examples,
        batch,
        pool="A",
        catalog=catalog,
        distribution=pi,
        loss=loss,
        annotations=annotations,
        **kwargs,
    )


def package_objective(model, package, annotation, objective, profile):
    grouped = {layer: [] for layer in p.LAYERS}
    tokens = []
    for source, sidecar in zip(package["rows"], annotation["rows"], strict=True):
        row = source["representation"]
        ids = torch.tensor(row["input_ids"])
        states = ids.cumsum(0) % 5
        for index, active in enumerate(row["target_mask"]):
            if not active:
                continue
            token = F.cross_entropy(
                model.table[states[index - 1]].float().reshape(1, -1), ids[index].reshape(1)
            )
            tokens.append(token)
            for layer in p.LAYERS:
                if sidecar["layer_masks"][layer][index]:
                    grouped[layer].append(token)
    if objective == "full_token_mean":
        return torch.stack(tokens).mean()
    return sum(
        float(Fraction(p.WEIGHTS[profile][layer])) * torch.stack(values).mean()
        for layer, values in grouped.items()
        if values
    )


def batch_objective(model, data, objective, profile):
    examples, _, _, pi, annotations = data
    terms = []
    for package in examples:
        outer = Fraction(pi[package["task_id"]][package["state_id"]]) / (
            5 * package["n_train_in_state"]
        )
        terms.append(
            float(outer)
            * package_objective(
                model, package, annotations[package["package_id"]], objective, profile
            )
        )
    return torch.stack(terms).sum()


@pytest.mark.parametrize("profile", p.PROFILES)
def test_full_class_gradient_is_exact_parent_delegate(profile, toy_materials):
    data = inputs(toy_materials, profile)
    examples, _, _, _, annotations = data
    first, second = Tiny(), Tiny()
    expected = original_gradients.class_gradients(first, examples)
    actual = live.class_gradients(
        second,
        examples,
        loss=HierarchicalTrajectoryLoss("full_token_mean", profile),
        annotations=annotations,
    )
    for task, states in expected["gradients"].items():
        for state, values in states.items():
            for name, gradient in values.items():
                assert torch.equal(gradient, actual["gradients"][task][state][name])
    assert actual["artifact"]["parent_full_delegate"] == expected["artifact"]
    assert first.calls == second.calls
    assert not actual["artifact"]["actual_Qwen_training"]


@pytest.mark.parametrize("profile", p.PROFILES)
def test_full_step_is_exact_parent_consumer_regression(profile, toy_materials):
    data = inputs(toy_materials, profile)
    examples, batch, catalog, pi, _ = data
    first, second = Tiny(), Tiny()
    first_opt, second_opt = CountingAdam(first), CountingAdam(second)
    expected = original.execute_update(
        first, first_opt, examples, batch, pool="A", catalog=catalog, distribution=pi
    )
    actual = step(second, second_opt, data, HierarchicalTrajectoryLoss("full_token_mean", profile))
    assert expected == actual["original_consumer_result"]
    assert first.calls == second.calls
    assert torch.equal(first.table, second.table)
    assert torch.equal(first.table.grad, second.table.grad)
    assert live._equal(first_opt.state_dict(), second_opt.state_dict())
    assert actual["delegated_unchanged_parent_full_consumer"]


@pytest.mark.parametrize("profile", p.PROFILES)
@pytest.mark.parametrize("initial", [True, False])
def test_hierarchical_64_package_step_matches_independent_AdamW_and_pi_once(
    profile, initial, toy_materials
):
    data = inputs(toy_materials, profile, initial=initial)
    first, second = Tiny(), Tiny()
    actual_opt, reference_opt = CountingAdam(first), CountingAdam(second)
    reference_opt.zero_grad(set_to_none=True)
    objective = batch_objective(second, data, "hierarchical", profile)
    objective.backward()
    torch.nn.utils.clip_grad_norm_(second.parameters(), 1.0)
    reference_opt.step()
    events = []
    result = step(
        first,
        actual_opt,
        data,
        HierarchicalTrajectoryLoss("hierarchical", profile),
        event_sink=events.append,
    )
    torch.testing.assert_close(first.table, second.table, atol=2e-7, rtol=1e-6)
    torch.testing.assert_close(first.table.grad, second.table.grad, atol=3e-7, rtol=1e-5)
    assert result["weighted_loss"] == pytest.approx(float(objective.detach()), abs=8e-7)
    assert actual_opt.zero_calls == actual_opt.step_calls == 1
    assert result["packages_completed"] == 64 and result["backward_calls"] == 256
    assert result["clip_calls"] == result["optimizer_step_calls"] == 1
    assert [call[0][0] for call in first.calls] == [
        row["representation"]["input_ids"] for package in data[0] for row in package["rows"]
    ]
    assert all(call[1] == [0, 1] for call in first.calls)
    assert (
        next(e for e in events if e["event"] == "before_single_optimizer_step")[
            "packages_completed"
        ]
        == 64
    )
    mass = sum(
        sum(Fraction(weight) for row in package["effective_target_coefficients"] for weight in row)
        for package in result["effective_coefficients"]
    )
    assert mass == (Fraction(1) if profile == "public_rtf" else Fraction(7, 10))
    assert result["adaptive_pi_updates"] == result["feedback_or_C_formula_calls"] == 0


def unequal_packages(profile):
    packages, annotations = [], {}
    for index, sizes in enumerate(((1, 2, 1), (3, 1, 2))):
        if profile == "public_tf":
            sizes = (0, sizes[0] + sizes[1], sizes[2])
        layers = [layer for layer, count in zip(p.LAYERS, sizes, strict=True) for _ in range(count)]
        ids = [1] + [(index + position) % 6 + 1 for position in range(len(layers))]
        mask = [0] + [1] * len(layers)
        row = {
            "candidate_id": "synthetic-candidate-" + str(index),
            "representation": {
                "input_ids": ids,
                "attention_mask": [1] * len(ids),
                "target_mask": mask,
                "labels": [-100] + ids[1:],
                "sequence_length": len(ids),
                "target_token_count": len(layers),
            },
        }
        package = {
            "package_id": "synthetic-package-" + str(index),
            "task_id": "x",
            "state_id": "z",
            "pool": "A",
            "role": "train",
            "state_catalog_id": "synthetic-catalog",
            "n_train_in_state": 2,
            "whole_package_target_tokens": len(layers),
            "rows": [row],
            "original_rows_sha256": p.sha(p.encode([row])),
            "target_token_coefficient": "1/100",
            "state_probability": "1",
        }
        masks = {layer: [0] + [int(value == layer) for value in layers] for layer in p.LAYERS}
        packages.append(package)
        annotations[package["package_id"]] = build_synthetic_package_annotation(
            package, [masks], profile=profile
        )
    return packages, annotations


@pytest.mark.parametrize("objective", p.OBJECTIVES)
@pytest.mark.parametrize("profile", p.PROFILES)
def test_unequal_package_lengths_use_package_mean_and_match_finite_difference(objective, profile):
    packages, annotations = unequal_packages(profile)
    model = Tiny()
    actual = live.class_gradients(
        model,
        packages,
        loss=HierarchicalTrajectoryLoss(objective, profile),
        annotations=annotations,
    )["gradients"]["x"]["z"]["table"]
    values = [
        package_objective(model, package, annotations[package["package_id"]], objective, profile)
        for package in packages
    ]
    independent = torch.stack(values).mean()
    expected = torch.autograd.grad(independent, model.table)[0]
    torch.testing.assert_close(actual, expected, atol=1e-7, rtol=1e-6)
    if objective == "full_token_mean":
        wrong = sum(
            value * package["whole_package_target_tokens"]
            for value, package in zip(values, packages, strict=True)
        ) / sum(package["whole_package_target_tokens"] for package in packages)
        assert abs(float((wrong - independent).detach())) > 1e-4
    direction = torch.linspace(-0.3, 0.4, model.table.numel()).reshape_as(model.table)
    original_point = model.table.detach().clone()
    delta, numeric = 0.005, []
    with torch.no_grad():
        for sign in (1, -1):
            model.table.copy_(original_point + sign * delta * direction)
            numeric.append(
                sum(
                    package_objective(
                        model, package, annotations[package["package_id"]], objective, profile
                    )
                    for package in packages
                ).item()
                / 2
            )
        model.table.copy_(original_point)
    assert (actual * direction).sum().item() == pytest.approx(
        (numeric[0] - numeric[1]) / (2 * delta), abs=3e-5, rel=3e-3
    )


@pytest.mark.parametrize("objective", p.OBJECTIVES)
def test_class_gradient_preserves_original_grads_buffers_and_mixed_dropout_modes(objective):
    packages, annotations = unequal_packages("public_rtf")
    model = Tiny()
    model.train()
    model.dropout.eval()
    model.table.grad = torch.full_like(model.table, 0.43)
    original_grad = model.table.grad
    before = live._snapshot(model)
    live.class_gradients(
        model, packages, loss=HierarchicalTrajectoryLoss(objective), annotations=annotations
    )
    live._unchanged(model, before, check_grads=True)
    assert model.table.grad is original_grad
    assert all(not call[2] for call in model.calls)


@pytest.mark.parametrize("objective", p.OBJECTIVES)
def test_class_gradient_rejects_buffer_mutation_and_restores_caller_state(objective):
    packages, annotations = unequal_packages("public_rtf")
    model = Tiny()
    model.mutate_buffer = True
    before = live._snapshot(model)
    with pytest.raises(ValueError, match="buffer"):
        live.class_gradients(
            model, packages, loss=HierarchicalTrajectoryLoss(objective), annotations=annotations
        )
    live._unchanged(model, before, check_grads=True)


@pytest.mark.parametrize("objective", p.OBJECTIVES)
def test_caller_alias_mutation_cannot_reweight_validated_inputs(objective, toy_materials):
    data = inputs(toy_materials)
    snapshot = copy.deepcopy(data)
    first, second = Tiny(), Tiny()
    reference = step(first, CountingAdam(first), data, HierarchicalTrajectoryLoss(objective))

    def mutate(event):
        if event["event"] == "validated_state_update":
            data[0][0]["target_token_coefficient"] = "9999"
            data[0][0]["rows"][0]["representation"]["input_ids"][0] = 6
            data[4].clear()
            data[3].clear()

    actual = step(
        second, CountingAdam(second), data, HierarchicalTrajectoryLoss(objective), event_sink=mutate
    )
    assert snapshot != data
    assert actual["weighted_loss"] == reference["weighted_loss"]
    assert torch.equal(first.table, second.table)
    assert actual["effective_coefficients"] == reference["effective_coefficients"]


@pytest.mark.parametrize("objective", p.OBJECTIVES)
@pytest.mark.parametrize(
    "bad", ["drop", "reorder", "rows", "heldout", "pool", "pending", "count", "pi_squared"]
)
def test_invalid_original_package_or_double_pi_stops_before_forward_and_zero(
    objective, bad, toy_materials
):
    data = inputs(toy_materials)
    examples, _, catalog, pi, _ = data
    if bad == "drop":
        examples.pop()
    elif bad == "reorder":
        examples.reverse()
    elif bad == "rows":
        examples[0]["rows"][0]["representation"]["input_ids"][0] += 1
    elif bad == "heldout":
        examples[0]["role"] = "heldout"
    elif bad == "pool":
        examples[0]["pool"] = "B"
    elif bad == "pending":
        catalog["status"] = "PENDING_REVIEW"
    elif bad == "count":
        examples[0]["n_train_in_state"] += 1
    else:
        examples[0]["target_token_coefficient"] = str(
            Fraction(examples[0]["target_token_coefficient"])
            * Fraction(pi[examples[0]["task_id"]][examples[0]["state_id"]])
        )
    model = Tiny()
    optimizer = CountingAdam(model)
    with pytest.raises(ValueError):
        step(model, optimizer, data, HierarchicalTrajectoryLoss(objective))
    assert optimizer.zero_calls == optimizer.step_calls == 0
    assert model.calls == []


@pytest.mark.parametrize("objective", p.OBJECTIVES)
@pytest.mark.parametrize(
    "failure", ["sink", "nonfinite", "buffer", "optimizer_mutation", "gradient_mutation"]
)
def test_failures_restore_state_and_never_step(objective, failure, toy_materials):
    data = inputs(toy_materials)
    model = Tiny()
    model.table.grad = torch.full_like(model.table, 0.23)
    optimizer = CountingAdam(model)
    before = live._snapshot(model)
    opt_before = copy.deepcopy(optimizer.state_dict())
    if failure == "nonfinite":
        model.nonfinite = True
    if failure == "buffer":
        model.mutate_buffer = True

    def callback(event):
        if event["event"] == "before_single_optimizer_step":
            if failure == "sink":
                raise RuntimeError("synthetic pre-step sink failure")
            if failure == "optimizer_mutation":
                optimizer.param_groups[0]["lr"] = 0.9
            if failure == "gradient_mutation":
                model.table.grad.mul_(2)

    with pytest.raises((ValueError, RuntimeError)):
        step(model, optimizer, data, HierarchicalTrajectoryLoss(objective), event_sink=callback)
    assert optimizer.step_calls == 0
    live._unchanged(model, before, check_grads=True)
    assert live._equal(optimizer.state_dict(), opt_before)


@pytest.mark.parametrize("objective", p.OBJECTIVES)
def test_missing_positive_layer_blocks_both_conditions_before_zero(objective, toy_materials):
    data = inputs(toy_materials)
    package = data[0][0]
    candidate = build_synthetic_package_annotation(
        package, ["tools", "tools", "tools", "final"], profile="public_tf"
    )
    data[4][package["package_id"]] = p.record(
        "package_layer_annotation",
        **{
            key: ("public_rtf" if key == "profile" else value)
            for key, value in candidate.items()
            if key not in {"id", "schema_version"}
        },
    )
    model = Tiny()
    optimizer = CountingAdam(model)
    with pytest.raises(ValueError):
        step(model, optimizer, data, HierarchicalTrajectoryLoss(objective))
    assert optimizer.zero_calls == optimizer.step_calls == 0 and not model.calls


def test_missing_member_of_a_class_rejected_before_class_forward():
    packages, annotations = unequal_packages("public_rtf")
    model = Tiny()
    with pytest.raises(ValueError, match="complete_original_class"):
        live.class_gradients(
            model, packages[:-1], loss=HierarchicalTrajectoryLoss(), annotations=annotations
        )
    assert not model.calls


def test_GPU_device_is_rejected_without_allocating_GPU_or_forward(toy_materials):
    data = inputs(toy_materials)
    model = Tiny()
    optimizer = CountingAdam(model)
    with pytest.raises(ValueError, match="CPU_only_no_production"):
        step(model, optimizer, data, HierarchicalTrajectoryLoss(), device="cuda")
    assert not model.calls and optimizer.step_calls == optimizer.zero_calls == 0


@pytest.mark.parametrize("objective", p.OBJECTIVES)
def test_duplicate_optimizer_parameter_cannot_apply_two_updates_per_step(objective, toy_materials):
    data = inputs(toy_materials)
    model = Tiny()
    optimizer = CountingAdam(model)
    optimizer.param_groups[0]["params"].append(model.table)
    with pytest.raises(ValueError, match="exact_trainable_optimizer_parameter_set"):
        step(model, optimizer, data, HierarchicalTrajectoryLoss(objective))
    assert optimizer.zero_calls == optimizer.step_calls == 0 and not model.calls


@pytest.mark.parametrize("objective", p.OBJECTIVES)
def test_readonly_class_gradient_does_not_increment_original_tensor_versions(objective):
    packages, annotations = unequal_packages("public_rtf")
    model = Tiny()
    model.table.grad = torch.full_like(model.table, 0.25)
    versions = (model.table._version, model.scale._version, model.table.grad._version)
    live.class_gradients(
        model, packages, loss=HierarchicalTrajectoryLoss(objective), annotations=annotations
    )
    assert versions == (model.table._version, model.scale._version, model.table.grad._version)
