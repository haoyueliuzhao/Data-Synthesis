"""Small CPU controls only: target loss/gradient, cache rejection, dose/config."""

from collections import Counter
from copy import deepcopy
from fractions import Fraction
from types import SimpleNamespace

import numpy as np
import pytest
import torch

from trusted_synthesis.experiments.finance_qa_vnext_fixed_kernel_value import population
from trusted_synthesis.experiments.finance_qa_vnext_fixed_kernel_value import protocol as p
from trusted_synthesis.experiments.finance_qa_vnext_fixed_kernel_value import training as original
from trusted_synthesis.experiments.finance_qa_vnext_fixed_kernel_value import trajectory_consumer as c
from trusted_synthesis.experiments.finance_qa_vnext_fixed_kernel_value import trajectory_training as t
from trusted_synthesis.experiments.finance_qa_vnext_pq_student.loss import selected_target_loss


class TinyCausal(torch.nn.Module):
    """Prefix-stable causal computation, deliberately no dropout/CUDA/checkpoint."""

    def __init__(self):
        super().__init__()
        self.embedding = torch.nn.Embedding(11, 5)
        self.projection = torch.nn.Linear(5, 11)

    def forward(self, input_ids, attention_mask, use_cache, logits_to_keep):
        hidden = self.embedding(input_ids).cumsum(dim=1)
        return SimpleNamespace(logits=self.projection(hidden[:, logits_to_keep]))


class SyntheticCache:
    cache_id = "explicit_synthetic_cpu_cache"

    def __init__(self, rows):
        self.rows = rows

    def row_arrays(self, package):
        for ids, positions in self.rows[package]:
            ids, positions = np.array(ids, dtype=np.int32), np.array(positions, dtype=np.int32)
            ids.flags.writeable = positions.flags.writeable = False
            yield {"input_ids": ids, "target_positions": positions, "target_ids": ids[positions]}


def test_prefix_union_and_nonprefix_fallback_match_original_weighted_loss_and_gradient():
    threads = torch.get_num_threads()
    torch.set_num_threads(1)
    try:
        torch.manual_seed(11)
        baseline = TinyCausal()
        fused = deepcopy(baseline)
        original_rows = {
            "prefix": [([1, 2, 3, 4], [2, 3]), ([1, 2, 3, 4, 5, 6, 7], [5, 6])],
            "nonprefix": [([1, 3, 4, 5], [2, 3]), ([2, 4, 6, 7, 2], [3, 4])],
        }
        cache = SyntheticCache({
            "prefix": [([1, 2, 3, 4, 5, 6, 7], [2, 3, 5, 6])],
            "nonprefix": original_rows["nonprefix"],
        })
        coefficients = {"prefix": Fraction(1, 80), "nonprefix": Fraction(1, 60)}
        examples = [
            {
                "package_id": key, "whole_package_target_tokens": 4,
                "target_token_coefficient": str(value), "coefficient_float": float(value),
            }
            for key, value in coefficients.items()
        ]
        expected = 0.0
        for name, rows in original_rows.items():
            for ids, targets in rows:
                ids = torch.tensor([ids])
                positions = torch.tensor(targets)
                logits = baseline(
                    ids, torch.ones_like(ids), False, positions - 1
                ).logits
                loss = selected_target_loss(logits, ids[0, positions], str(coefficients[name]))
                expected += float(loss.detach())
                loss.backward()
        norm = torch.nn.utils.clip_grad_norm_(baseline.parameters(), 1.0, error_if_nonfinite=True)
        optimizer = torch.optim.SGD(fused.parameters(), lr=0)
        events = []
        report = c.execute_update(
            fused, optimizer, examples, {"tasks": []}, pool="A", arm="plus",
            device=torch.device("cpu"), trajectory_cache=cache, event_sink=events.append,
        )
        assert report["weighted_loss"] == pytest.approx(expected, abs=1e-7)
        assert report["preclip_gradient_norm"] == pytest.approx(float(norm), abs=1e-7)
        for reference, actual in zip(baseline.parameters(), fused.parameters(), strict=True):
            torch.testing.assert_close(actual.grad, reference.grad, atol=1e-7, rtol=1e-6)
        assert report["target_tokens"] == 8
        assert report["sequence_tokens"] == 16  # Original rows process 20 tokens.
        assert report["rows_completed"] == 3
        assert report["packages_completed"] == 2
        assert report["zero_grad_calls"] == report["clip_calls"] == report["optimizer_step_calls"] == 1
        assert [row["package_id"] for row in report["package_losses"]] == ["prefix", "nonprefix"]
        assert events[-1]["event"] == "update_complete"
    finally:
        torch.set_num_threads(threads)


def test_nonfinite_loss_aborts_before_optimizer_step():
    model = TinyCausal()
    optimizer = torch.optim.AdamW(model.parameters())
    cache = SyntheticCache({"bad": [([1, 2, 3], [1, 2])]})

    def nonfinite(logits, targets, coefficient):
        return c.selected_target_loss(logits, targets, coefficient) * float("nan")

    # Record encoding also rejects nonfinite values; with no event writer the
    # optimizer boundary itself must independently reject the accumulated loss.
    with pytest.raises(ValueError, match="finite_update_loss"):
        c.execute_update(
            model, optimizer, [{"package_id": "bad", "coefficient_float": 0.1}],
            {"tasks": []}, pool="A", arm="plus", device="cpu", trajectory_cache=cache,
            loss_fn=nonfinite,
        )
    assert not optimizer.state


def test_forged_cache_is_rejected_before_distribution_or_model_loading(monkeypatch):
    # The material module's real private-mint guard runs; only the independent
    # parent authority guard is bypassed in this explicitly synthetic test.
    monkeypatch.setattr(t.fast_materials, "require_verified", lambda value: value)
    monkeypatch.setattr(
        t.distribution, "distribution", lambda *_args: pytest.fail("distribution before cache gate")
    )
    with pytest.raises((ValueError, TypeError, AttributeError)):
        t.weighted_inputs({}, "A", "plus", SyntheticCache({}))


def test_physical_settings_and_original_paired_400_update_schedule_are_unchanged():
    from test_qa_vnext_fixed_kernel_distribution import catalog

    config, previous = t.training_config(), original.training_config()
    for key in (
        "model", "base_dtype", "adapter_dtype", "optimizer_state_dtype", "lora_rank",
        "lora_alpha", "lora_dropout", "target_modules", "optimizer", "learning_rate",
        "betas", "eps", "weight_decay", "maximum_gradient_norm", "epochs", "task_count",
        "optimizer_updates", "tasks_per_update", "maximum_sequence_length", "truncation",
        "gradient_checkpointing", "use_reentrant", "attention_implementation", "sdpa_backend",
        "token_coefficient", "paired_initialization_and_schedule", "extra_global_N_or_token_or_microbatch_divisor",
    ):
        assert config[key] == previous[key]
    assert config["id"] != previous["id"]
    assert config["resume_paused_response_row_optimizer"] is False
    assert t.optimizer_factory is original.optimizer_factory
    selected = population.make_population(catalog())
    for seed in p.SEEDS:
        schedule = t.population.batch_schedule(selected, seed)
        assert schedule == original.population.batch_schedule(selected, seed)
        assert schedule["total_updates"] == len(schedule["batches"]) == 400
        assert Counter(
            task for batch in schedule["batches"] for task in batch["task_ids"]
        ) == Counter({task["task_id"]: 10 for task in selected["tasks"]})
