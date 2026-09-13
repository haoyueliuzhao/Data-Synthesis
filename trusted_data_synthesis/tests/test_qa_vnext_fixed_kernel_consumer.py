"""Unequal-count Full-loss controls: independent gradients, no GPU or API."""

import copy
from collections import defaultdict
from fractions import Fraction
from types import SimpleNamespace

import pytest
import torch
import torch.nn.functional as functional

from trusted_synthesis.experiments.finance_qa_vnext_basis_student.protocol import (
    training_config as old_config,
)
from trusted_synthesis.experiments.finance_qa_vnext_fixed_kernel_value import consumer as c
from trusted_synthesis.experiments.finance_qa_vnext_fixed_kernel_value import gpu_preflight
from trusted_synthesis.experiments.finance_qa_vnext_fixed_kernel_value import protocol as p
from trusted_synthesis.experiments.finance_qa_vnext_fixed_kernel_value import training as t


class TinyStudent(torch.nn.Module):
    def __init__(self):
        super().__init__()
        self.adapter = torch.nn.Module()
        self.adapter.lora_A = torch.nn.Parameter(torch.linspace(-0.2, 0.2, 100))

    def forward(self, input_ids, attention_mask, use_cache, logits_to_keep):
        assert use_cache is False
        assert torch.equal(attention_mask, torch.ones_like(input_ids))
        return SimpleNamespace(
            logits=self.adapter.lora_A.view(1, 1, -1).expand(1, logits_to_keep.numel(), -1)
        )


class TrackingAdamW(torch.optim.AdamW):
    def __init__(self, parameters):
        super().__init__(parameters, lr=1e-4, betas=(0.9, 0.999), eps=1e-8, weight_decay=0.0)
        self.steps = 0
        self.zeros = 0

    def zero_grad(self, *args, **kwargs):
        self.zeros += 1
        return super().zero_grad(*args, **kwargs)

    def step(self, *args, **kwargs):
        self.steps += 1
        self.pre_step_gradients = [
            parameter.grad.clone() for group in self.param_groups for parameter in group["params"]
        ]
        return super().step(*args, **kwargs)


def controls():
    batch, examples = gpu_preflight.controls(512)
    # Exercise heterogeneous rows too: a whole package need not be a single row.
    examples[1]["rows"].append(copy.deepcopy(examples[0]["rows"][0]))
    examples[1]["whole_package_target_tokens"] += examples[0]["whole_package_target_tokens"]
    examples[1]["target_token_coefficient"] = str(
        Fraction(examples[1]["pi"])
        / (5 * examples[1]["n_state"] * examples[1]["whole_package_target_tokens"])
    )
    return batch, examples


def execute(model=None, optimizer=None, **kwargs):
    batch, examples = controls()
    model = model or TinyStudent()
    optimizer = optimizer or TrackingAdamW(model.parameters())
    result = c.execute_update(
        model,
        optimizer,
        examples,
        batch,
        pool="A",
        arm="plus",
        device="cpu",
        expected_package_ids=[row["package_id"] for row in examples],
        engineering_only=True,
        **kwargs,
    )
    return model, optimizer, result


def test_unequal_15_packages_independent_grouped_loss_gradient_and_adamw():
    batch, examples = controls()
    model = TinyStudent()
    reference = copy.deepcopy(model)
    grouped = defaultdict(list)
    masses = {}
    for package in examples:
        nll = torch.tensor(0.0)
        for row in package["rows"]:
            representation = row["representation"]
            labels = representation["labels"]
            targets = torch.tensor([label for label in labels if label != -100])
            logits = reference.adapter.lora_A.expand(targets.numel(), -1)
            nll = nll + functional.cross_entropy(logits, targets, reduction="sum")
        key = package["task_id"], package["state_id"]
        grouped[key].append(nll / package["whole_package_target_tokens"])
        masses[key] = Fraction(package["pi"])
    objective = (
        sum(torch.stack(means).mean() * float(masses[key]) for key, means in grouped.items()) / 5
    )
    reference_optimizer = TrackingAdamW(reference.parameters())
    reference_optimizer.zero_grad(set_to_none=True)
    objective.backward()
    reference_norm = torch.nn.utils.clip_grad_norm_(reference.parameters(), 1.0)
    reference_optimizer.step()
    optimizer = TrackingAdamW(model.parameters())
    _, optimizer, result = execute(model, optimizer)
    assert result["physical_package_count"] == 15 != 64
    assert result["rows_completed"] == 16
    assert result["packages_completed"] == 15
    assert result["weighted_loss"] == pytest.approx(float(objective.detach()), rel=1e-6)
    assert result["preclip_gradient_norm"] == pytest.approx(float(reference_norm), rel=1e-6)
    torch.testing.assert_close(
        optimizer.pre_step_gradients[0], reference_optimizer.pre_step_gradients[0]
    )
    torch.testing.assert_close(model.adapter.lora_A, reference.adapter.lora_A)
    assert optimizer.steps == optimizer.zeros == 1
    assert result["clip_calls"] == result["optimizer_step_calls"] == result["zero_grad_calls"] == 1
    assert result["loss_domain"] == "Full_original_target_mask"
    assert result["additional_loss_scaling"] is False


def test_all_rows_backward_before_clip_and_step():
    events = []
    _, optimizer, result = execute(event_sink=events.append)
    before_step = next(event for event in events if event["event"] == "before_optimizer_step")
    assert before_step["rows_completed"] == 16
    assert before_step["packages_completed"] == 15
    assert before_step["optimizer_step_calls"] == 0
    assert events[-1]["optimizer_step_calls"] == optimizer.steps == 1


def test_failed_persistent_before_step_aborts_without_optimizer_step():
    model = TinyStudent()
    optimizer = TrackingAdamW(model.parameters())

    def failing_sink(event):
        if event["event"] == "before_optimizer_step":
            raise OSError("synthetic durable evidence failure")

    with pytest.raises(OSError, match="durable"):
        execute(model, optimizer, event_sink=failing_sink)
    assert optimizer.steps == 0
    assert optimizer.zeros == 1
    assert not optimizer.state


@pytest.mark.parametrize(
    "mutation,code",
    [
        (lambda rows, batch: rows.pop(), "inventory"),
        (lambda rows, batch: rows.reverse(), "inventory"),
        (lambda rows, batch: rows[0].update(role="sealed"), "holdout"),
        (lambda rows, batch: rows[0].update(pool="B"), "other_pool"),
        (lambda rows, batch: rows[0].update(n_state=8), "state_count"),
        (lambda rows, batch: rows[0].update(pi=0.5), "exact_fraction"),
        (lambda rows, batch: rows[0].update(whole_package_target_tokens=1), "denominator"),
        (lambda rows, batch: rows[0].update(target_token_coefficient="1/64"), "no_extra_scale"),
        (
            lambda rows, batch: rows[0]["rows"][0]["representation"]["target_mask"].__setitem__(
                0, 1
            ),
            "causal",
        ),
        (
            lambda rows, batch: rows[0]["rows"][0]["representation"].update(truncation=True),
            "truncated",
        ),
        (lambda rows, batch: batch["tasks"][0].update(group="control"), "target_two_controls"),
    ],
)
def test_rejects_silent_legacy_accounting_or_physical_changes(mutation, code):
    batch, examples = controls()
    expected = [row["package_id"] for row in examples]
    mutation(examples, batch)
    with pytest.raises(ValueError, match=code):
        c.validate_update(
            examples,
            batch,
            pool="A",
            arm="plus",
            expected_package_ids=expected,
            engineering_only=True,
        )


def test_missing_independent_inventory_is_not_accepted():
    batch, examples = controls()
    with pytest.raises(ValueError, match="inventory"):
        c.validate_update(examples, batch, pool="A", arm="plus", engineering_only=True)


def test_exact_each_task_mass_even_with_unequal_package_and_target_counts():
    batch, examples = controls()
    metadata = c.validate_update(
        examples,
        batch,
        pool="A",
        arm="plus",
        expected_package_ids=[row["package_id"] for row in examples],
        engineering_only=True,
    )
    mass = defaultdict(Fraction)
    for row in metadata:
        mass[row["task_id"]] += (
            Fraction(row["target_token_coefficient"]) * row["whole_package_target_tokens"]
        )
    assert len(mass) == 5 and set(mass.values()) == {Fraction(1, 5)}


def test_synthetic_controls_are_not_admitted_by_default_production_consumer():
    batch, examples = controls()
    with pytest.raises(ValueError, match="production_original_identity"):
        c.validate_update(
            examples,
            batch,
            pool="A",
            arm="plus",
            expected_package_ids=[row["package_id"] for row in examples],
        )


def test_configuration_preserves_baseline_physics_but_replaces_old_admin():
    old, new = old_config(), t.training_config()
    keys = (
        "model",
        "base_dtype",
        "adapter_dtype",
        "optimizer_state_dtype",
        "lora_rank",
        "lora_alpha",
        "lora_dropout",
        "target_modules",
        "optimizer",
        "learning_rate",
        "betas",
        "eps",
        "weight_decay",
        "maximum_gradient_norm",
        "scheduler",
        "warmup_steps",
        "seeds",
        "epochs",
        "maximum_sequence_length",
        "truncation",
        "microbatch_rows",
        "attention_implementation",
        "sdpa_backend",
        "gradient_checkpointing",
        "use_reentrant",
        "training_use_cache",
        "causal_shift",
        "loss_dtype",
        "allow_tf32",
        "deterministic_algorithms",
        "checkpoint_selection",
    )
    assert all(old[key] == new[key] for key in keys)
    assert new["optimizer_updates"] == 400 and new["task_count"] == 200
    assert new["packages_per_update"] != 64
    assert "training_packages_per_task_method" not in new
    assert "heldout_packages_per_task_method" not in new
    assert new["HierLoss_or_TF_global_scaling"] is False
    assert new["old_fixed_64_package_or_8_plus_2_administration"] is False


@pytest.mark.parametrize("length", (0, 63, 24577, 65536))
def test_engineering_controls_have_bounded_unchanged_sequence_cap(length):
    with pytest.raises(ValueError, match="bounded"):
        gpu_preflight.controls(length)


def test_failed_material_gate_cannot_make_release():
    kernel = p.record("fixed_kernel", training_gate="FAIL", material_gate="PASS", dose_gate="FAIL")
    with pytest.raises(ValueError, match="both_gates"):
        t.make_release(
            kernel, study_freeze_id="test", surface_manifest_id="surface", allowed_runs=[]
        )


def test_failure_before_admission_never_loads_student(tmp_path):
    called = []

    def forbidden_loader(*args, **kwargs):
        called.append(True)
        raise AssertionError("must not load")

    kernel = p.record("fixed_kernel", training_gate="FAIL", material_gate="FAIL", dose_gate="FAIL")
    with pytest.raises(ValueError):
        t.run(
            tmp_path,
            tmp_path / "failed_run",
            kernel,
            {},
            {},
            [],
            {},
            {},
            pool="A",
            arm="alpha0",
            seed=11,
            model_loader=forbidden_loader,
        )
    assert called == []
    failure = p.read_json(tmp_path / "failed_run" / "failure.json")
    assert failure["actual_complete"] is False and failure["completed_updates"] == []
    with pytest.raises(ValueError, match="no_retry"):
        t.run(
            tmp_path,
            tmp_path / "failed_run",
            kernel,
            {},
            {},
            [],
            {},
            {},
            pool="A",
            arm="alpha0",
            seed=11,
            model_loader=forbidden_loader,
        )
