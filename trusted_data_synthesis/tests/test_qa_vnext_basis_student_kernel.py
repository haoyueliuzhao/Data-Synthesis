"""CPU-only exact-objective controls; no checkpoint or tokenizer is loaded."""

import copy
from collections import defaultdict
from fractions import Fraction
from types import SimpleNamespace

import pytest
import torch
from torch import nn
from torch.nn import functional as F

from trusted_synthesis.experiments.finance_qa_vnext_basis_scale_preparation import design
from trusted_synthesis.experiments.finance_qa_vnext_basis_student import kernel


@pytest.fixture(autouse=True)
def single_thread():
    previous = torch.get_num_threads()
    torch.set_num_threads(1)
    yield
    torch.set_num_threads(previous)


class TinyCausal(nn.Module):
    def __init__(self):
        super().__init__()
        self.table = nn.Parameter(torch.arange(35, dtype=torch.float32).reshape(5, 7) / 70)
        self.calls = []

    def forward(self, *, input_ids, attention_mask, use_cache, logits_to_keep):
        self.calls.append((input_ids.tolist()[0], logits_to_keep.tolist(), attention_mask.tolist()))
        assert use_cache is False
        # Every preceding token influences logits, including non-target history.
        state = input_ids.cumsum(-1) % 5
        return SimpleNamespace(logits=self.table[state][:, logits_to_keep, :])


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


def example_update(arm="alpha0"):
    tasks = [{"task_id": group, "group": group} for group in design.DUAL_GROUPS]
    tasks += [{"task_id": f"c{i}", "group": "control"} for i in range(2)]
    examples = []
    for task in tasks:
        for method in ("control",) if task["group"] == "control" else design.METHODS:
            for index in range(8):
                rows = []
                for row_index in range(1 + index % 3):
                    ids = [4, 2, 1 + row_index, 3, index % 7, 1]
                    mask = [0, 0, 1, int(index % 2 == 0), 1, 0]
                    rows.append(
                        {
                            "candidate_id": f"{index}-{row_index}",
                            "representation": {
                                "input_ids": ids,
                                "attention_mask": [1] * len(ids),
                                "target_mask": mask,
                                "labels": [
                                    token if active else -100
                                    for token, active in zip(ids, mask, strict=True)
                                ],
                                "sequence_length": len(ids),
                                "target_token_count": sum(mask),
                            },
                        }
                    )
                length = sum(row["representation"]["target_token_count"] for row in rows)
                examples.append(
                    {
                        "package_id": f"{task['task_id']}-{method}-{index}",
                        "task_id": task["task_id"],
                        "pool": "A",
                        "actual_method": method,
                        "whole_package_target_tokens": length,
                        "target_token_coefficient": str(
                            design.update_token_coefficient(arm, task["group"], method, length)
                        ),
                        "rows": rows,
                    }
                )
    return examples, {"tasks": tasks}


def independent_objective(model, examples, batch, arm):
    """Independent token -> package -> method -> task means; no kernel coefficients."""
    methods = defaultdict(list)
    for package in examples:
        losses, tokens = [], 0
        for row in package["rows"]:
            rep = row["representation"]
            ids = torch.tensor([rep["input_ids"]])
            full = model.table[ids.cumsum(-1) % 5][0]
            labels = torch.tensor(rep["labels"])
            losses.append(
                F.cross_entropy(full[:-1], labels[1:], ignore_index=-100, reduction="sum")
            )
            tokens += sum(rep["target_mask"])
        methods[package["task_id"], package["actual_method"]].append(sum(losses) / tokens)
    p = {"alpha0": Fraction(1, 2), "plus": Fraction(2, 3), "minus": Fraction(1, 3)}[arm]
    tasks = []
    for task in batch["tasks"]:
        if task["group"] == "control":
            tasks.append(torch.stack(methods[task["task_id"], "control"]).mean())
        else:
            tasks.append(
                float(1 - p) * torch.stack(methods[task["task_id"], "endpoint"]).mean()
                + float(p) * torch.stack(methods[task["task_id"], "movement"]).mean()
            )
    return torch.stack(tasks).mean()


@pytest.mark.parametrize("arm", design.ARMS)
def test_all_64_package_gradients_and_single_adam_step_match_independent_reduction(
    arm, monkeypatch
):
    examples, batch = example_update(arm)
    model, reference = TinyCausal(), TinyCausal()
    optimizer, other = CountingAdam(model.parameters()), CountingAdam(reference.parameters())
    other.zero_grad(set_to_none=True)
    expected = independent_objective(reference, examples, batch, arm)
    expected.backward()
    gradients = reference.table.grad.clone()
    clip = torch.nn.utils.clip_grad_norm_
    observed = []

    def inspect(parameters, *args, **kwargs):
        parameters = list(parameters)
        observed.append(parameters[0].grad.clone())
        return clip(parameters, *args, **kwargs)

    monkeypatch.setattr(torch.nn.utils, "clip_grad_norm_", inspect)
    events = []
    result = kernel.execute_update(
        model, optimizer, examples, batch, pool="A", arm=arm, device="cpu", event_sink=events.append
    )
    clip(reference.parameters(), 1.0, error_if_nonfinite=True)
    other.step()
    assert len(observed) == 1
    torch.testing.assert_close(observed[0], gradients, rtol=1e-5, atol=2e-7)
    torch.testing.assert_close(model.table, reference.table, rtol=1e-5, atol=2e-7)
    assert result["weighted_loss"] == pytest.approx(float(expected.detach()), rel=1e-6)
    assert optimizer.zero_calls == optimizer.step_calls == result["clip_calls"] == 1
    assert result["packages_completed"] == 64 and not result["extra_normalization"]
    assert result["rows_completed"] == sum(len(package["rows"]) for package in examples)
    assert result["target_tokens"] == sum(
        package["whole_package_target_tokens"] for package in examples
    )
    before_step = next(event for event in events if event["event"] == "optimizer_step_intent")
    assert before_step["packages_completed"] == 64 and before_step["optimizer_step_calls"] == 0
    for observed_call, row in zip(
        model.calls, [row for p in examples for row in p["rows"]], strict=True
    ):
        rep = row["representation"]
        assert observed_call[0] == rep["input_ids"]
        assert observed_call[1] == [i - 1 for i, active in enumerate(rep["target_mask"]) if active]
    assert result["causal_shift"] == 1


@pytest.mark.parametrize(
    "mutation,code",
    [
        (lambda rows, batch: rows.pop(), "exact_64"),
        (lambda rows, batch: rows[0].update(pool="B"), "no_mixed_pool"),
        (lambda rows, batch: rows[0].update(role="heldout"), "no_mixed_pool"),
        (lambda rows, batch: rows[0].update(whole_package_target_tokens=999), "denominator"),
        (lambda rows, batch: rows[0].update(target_token_coefficient="1/6400"), "normalization"),
        (lambda rows, batch: rows[0].update(actual_method="movement"), "eight_training"),
        (lambda rows, batch: rows[1].update(package_id=rows[0]["package_id"]), "unique_complete"),
        (lambda rows, batch: batch["tasks"][0].update(group="control"), "five_tasks"),
        (
            lambda rows, batch: rows[0]["rows"][0]["representation"]["target_mask"].__setitem__(
                0, 1
            ),
            "single_causal_shift",
        ),
        (
            lambda rows, batch: rows[0]["rows"][0]["representation"]["labels"].__setitem__(1, 2),
            "single_causal_shift",
        ),
        (
            lambda rows, batch: rows[0]["rows"][0]["representation"].update(attention_mask=[0] * 6),
            "unpadded_attention",
        ),
    ],
)
def test_malformed_kernel_never_zeroes_or_steps(mutation, code):
    examples, batch = example_update()
    mutation(examples, batch)
    model = TinyCausal()
    optimizer = CountingAdam(model.parameters())
    with pytest.raises(ValueError, match=code):
        kernel.execute_update(
            model, optimizer, examples, batch, pool="A", arm="alpha0", device="cpu"
        )
    assert optimizer.zero_calls == optimizer.step_calls == 0 and not model.calls


def test_nonfinite_loss_preserves_partial_history_and_does_not_step():
    examples, batch = example_update()
    model = TinyCausal()
    optimizer = CountingAdam(model.parameters())
    events, calls = [], []

    def bad_loss(logits, targets, coefficient):
        calls.append(1)
        if len(calls) == 4:
            return logits.sum() * float("nan")
        return kernel.selected_target_loss(logits, targets, coefficient)

    with pytest.raises(ValueError, match="finite_scalar_loss"):
        kernel.execute_update(
            model,
            optimizer,
            examples,
            batch,
            pool="A",
            arm="alpha0",
            device="cpu",
            loss_fn=bad_loss,
            event_sink=events.append,
        )
    assert optimizer.zero_calls == 1 and optimizer.step_calls == 0
    assert events[-1]["event"] == "update_failed" and events[-1]["rows_completed"] == 3
    assert len(calls) == 4


def test_nonfinite_gradient_cannot_reach_optimizer_step():
    examples, batch = example_update()
    model = TinyCausal()
    model.table.register_hook(lambda gradient: gradient * float("inf"))
    optimizer = CountingAdam(model.parameters())
    with pytest.raises(ValueError, match="finite_gradients"):
        kernel.execute_update(
            model, optimizer, examples, batch, pool="A", arm="alpha0", device="cpu"
        )
    assert optimizer.zero_calls == 1 and optimizer.step_calls == 0


def test_nonfinite_optimizer_state_cannot_reach_step():
    examples, batch = example_update()
    model = TinyCausal()
    optimizer = CountingAdam(model.parameters())
    optimizer.state[model.table]["exp_avg"] = torch.full_like(model.table, float("inf"))
    with pytest.raises(ValueError, match="finite_optimizer_state"):
        kernel.execute_update(
            model, optimizer, examples, batch, pool="A", arm="alpha0", device="cpu"
        )
    assert optimizer.zero_calls == 1 and optimizer.step_calls == 0


def test_frozen_package_order_is_not_length_sorted():
    examples, batch = example_update()
    expected = [package["package_id"] for package in examples]
    changed = copy.deepcopy(examples)
    changed[0], changed[1] = changed[1], changed[0]
    with pytest.raises(ValueError, match="frozen_training_package_order"):
        kernel.validate_update(
            changed, batch, pool="A", arm="alpha0", expected_package_ids=expected
        )


def test_durable_failure_before_step_intent_prevents_update():
    examples, batch = example_update()
    model = TinyCausal()
    optimizer = CountingAdam(model.parameters())

    def sink(event):
        if event["event"] == "optimizer_step_intent":
            raise OSError("synthetic disk failure")

    with pytest.raises(OSError, match="disk failure"):
        kernel.execute_update(
            model, optimizer, examples, batch, pool="A", arm="alpha0", device="cpu", event_sink=sink
        )
    assert optimizer.zero_calls == 1 and optimizer.step_calls == 0
