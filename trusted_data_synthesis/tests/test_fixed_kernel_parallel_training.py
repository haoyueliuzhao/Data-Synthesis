"""Two necessary CPU controls; CUDA native-mask/NCCL smoke is a separate one-shot."""

from copy import deepcopy

import pytest
import torch

from trusted_synthesis.experiments.finance_qa_vnext_fixed_kernel_value import parallel_training as t
from trusted_synthesis.experiments.finance_qa_vnext_fixed_kernel_value import (
    trajectory_training as serial,
)


def test_weighted_SUM_with_empty_ranks_matches_serial_global_clip_and_one_AdamW_step():
    torch.manual_seed(47)
    reference = torch.nn.Linear(3, 2)
    replicas = [deepcopy(reference) for _ in range(8)]
    examples = [
        (torch.tensor([[1.0, 2.0, 3.0]]), torch.tensor([[0.3, -0.1]]), 1 / 20),
        (torch.tensor([[0.5, -1.0, 0.2]]), torch.tensor([[0.2, 0.1]]), 1 / 15),
        (torch.tensor([[3.0, 2.0, 1.0]]), torch.tensor([[-0.5, 0.7]]), 1 / 30),
    ]
    config = serial.training_config()
    expected_optimizer = serial.optimizer_factory(reference.parameters(), config)
    expected_optimizer.zero_grad(set_to_none=True)
    for inputs, targets, coefficient in examples:
        ((reference(inputs) - targets).square().sum() * coefficient).backward()
    expected_norm = torch.nn.utils.clip_grad_norm_(reference.parameters(), 1.0)
    expected_optimizer.step()
    payloads, optimizers = [], []
    assignments = [[0, 2], [1], [], [], [], [], [], []]
    for model, indices in zip(replicas, assignments, strict=True):
        optimizer = serial.optimizer_factory(model.parameters(), config)
        optimizer.zero_grad(set_to_none=True)
        total = 0.0
        for index in indices:
            inputs, targets, coefficient = examples[index]
            loss = (model(inputs) - targets).square().sum() * coefficient
            loss.backward()
            total += float(loss.detach())
        payloads.append(
            t.pack_gradients(
                list(model.parameters()),
                [total, len(indices), 3 * len(indices), len(indices), len(indices)],
            )
        )
        optimizers.append(optimizer)
    global_sum = torch.stack(payloads).sum(dim=0)
    for model, optimizer in zip(replicas, optimizers, strict=True):
        norm, stats = t.install_sum_and_step(list(model.parameters()), optimizer, global_sum)
        assert norm == pytest.approx(float(expected_norm), abs=1e-6)
        assert stats[1:] == [3, 9, 3, 3]
        for expected, actual in zip(reference.parameters(), model.parameters(), strict=True):
            torch.testing.assert_close(actual, expected, atol=1e-7, rtol=1e-6)
        assert all(int(value["step"]) == 1 for value in optimizer.state.values())
    assert not torch.allclose(global_sum, global_sum / 8)


def test_partition_and_Philox_plan_preserve_serial_package_order_and_physical_configuration():
    packages = [
        {"package_id": str(index), "sequence_tokens": size, "segment_lengths": [size]}
        for index, size in enumerate((9, 3, 8, 2, 6))
    ]
    assignment, loads = t.partition_packages(packages, 8)
    assert sorted(index for rank in assignment for index in rank) == list(range(5))
    assert all(rank == sorted(rank) for rank in assignment)
    assert sum(loads) == 28
    calibration = {
        "initial_offset": 120,
        "calls_per_segment": 56,
        "per_dropout_call_offsets": {str(size): 4 * size for size in (9, 3, 8, 2, 6)},
    }
    plan = {
        "batches": [
            {"step": 0, "packages": packages, "rank_package_indices": assignment},
            {"step": 1, "packages": list(reversed(packages)), "rank_package_indices": assignment},
        ]
    }
    batches, final = t.attach_serial_offsets(plan, calibration)
    cursor = 120
    for batch in batches:
        for package in batch["packages"]:
            rng = package["rng_segments"][0]
            assert rng["offset"] == cursor
            cursor += 56 * 4 * package["sequence_tokens"]
            assert rng["end_offset"] == cursor
    assert cursor == final == 120 + 2 * 56 * 4 * 28
    config, previous = t.training_config(), serial.training_config()
    for key in (
        "model",
        "base_dtype",
        "adapter_dtype",
        "lora_rank",
        "lora_alpha",
        "lora_dropout",
        "target_modules",
        "optimizer",
        "learning_rate",
        "betas",
        "eps",
        "weight_decay",
        "epochs",
        "optimizer_updates",
        "tasks_per_update",
        "token_coefficient",
        "gradient_checkpointing",
        "sdpa_backend",
    ):
        assert config[key] == previous[key]
    assert config["parent_trajectory_training_configuration_id"] == previous["id"]
    assert config["parallel_rng_policy"]["per_package_reseeding"] is False
    assert config["parallel_policy"]["only_run"] == {"pool": "A", "arm": "minus", "seed": 47}
    assert config["bitwise_optimizer_equivalence_claimed"] is False
