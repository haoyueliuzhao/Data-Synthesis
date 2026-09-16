"""Check new virtual sampler checkpoint serialization without mutating Student."""

import importlib
import sys
from pathlib import Path

import torch
from safetensors.torch import load_file
from torch import nn

sys.path.insert(0, str(Path(__file__).parents[1] / "scripts"))
training = importlib.import_module("run_fixed_kernel_anchored_training_20260916")


def test_virtual_file_and_point_digest_use_virtual_values_not_restored_student(tmp_path):
    model = nn.Module()
    model.block = nn.Module()
    model.block.lora_A = nn.Parameter(torch.ones(2, 3))
    model.block.lora_B = nn.Parameter(torch.zeros(3, 2))
    before = {name: value.detach().clone() for name, value in model.named_parameters()}
    theta = {name: (value + 0.25).requires_grad_(True) for name, value in before.items()}
    plan = dict(
        source_manifest_id="manifest:source", assets=dict(base_binding=dict(id="binding:base"))
    )
    point = training.point_record(
        tmp_path,
        tmp_path / "virtual",
        model,
        theta,
        plan,
        dict(pool="A", seed=11, condition="full_anchored_vtdo"),
        step=0,
        kind="virtual_full_population_step",
        origin="virtual:step",
    )
    actual = load_file(str(tmp_path / "virtual/adapter.safetensors"))
    assert point["point_kind"] == "virtual_full_population_step"
    assert training.gate.tensor_digest(actual) == point["parameter_digest"]
    for name, value in model.named_parameters():
        assert torch.equal(actual[name], theta[name])
        assert torch.equal(value, before[name]) and value.grad is None
    assert model.training
