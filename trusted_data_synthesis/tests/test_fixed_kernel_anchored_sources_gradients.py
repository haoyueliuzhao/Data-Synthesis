"""One unequal-count full-population numerical control, not a real-model claim."""

import importlib
import sys
from pathlib import Path
from types import SimpleNamespace

import torch
from torch import nn

sys.path.insert(0, str(Path(__file__).parents[1] / "scripts"))
core = importlib.import_module("fixed_kernel_anchored_sources_gradients_20260916")


def test_original_package_class_mean_full_G_controls_and_centering():
    class Tiny(nn.Module):
        def __init__(self):
            super().__init__()
            self.weight = nn.Parameter(torch.arange(9, dtype=torch.float32).reshape(3, 3) / 7)
            self.dropout = nn.Dropout(0.05)

        def forward(self, input_ids, attention_mask, use_cache, logits_to_keep):
            x = torch.nn.functional.one_hot(input_ids, num_classes=3).float()
            return SimpleNamespace(logits=(self.dropout(x) @ self.weight)[:, logits_to_keep, :])

    packages = [
        dict(package_id="a", task_id="x", state_id="s", whole_package_target_tokens=2),
        dict(package_id="b", task_id="x", state_id="s", whole_package_target_tokens=1),
        dict(package_id="c", task_id="x", state_id="t", whole_package_target_tokens=1),
        dict(package_id="d", task_id="control", state_id="c", whole_package_target_tokens=2),
    ]
    rows = {
        "a": [dict(input_ids=[0, 1, 2], target_positions=[1, 2], target_ids=[1, 2])],
        "b": [dict(input_ids=[2, 1], target_positions=[1], target_ids=[1])],
        "c": [dict(input_ids=[1, 0], target_positions=[1], target_ids=[0])],
        "d": [
            dict(input_ids=[1, 2], target_positions=[1], target_ids=[2]),
            dict(input_ids=[2, 0], target_positions=[1], target_ids=[0]),
        ],
    }
    cache = SimpleNamespace(packages=packages, row_arrays=rows.__getitem__)
    pi = {"x": {"s": "2/3", "t": "1/3"}, "control": {"c": "1"}}
    mu = {"x": "1/2", "control": "1/2"}
    model = Tiny()
    model.weight.grad = torch.full_like(model.weight, 7)
    before = model.weight.detach().clone()
    rng = torch.get_rng_state().clone()
    actual = core._compute(model, cache, pi, mu)
    independent = torch.zeros((), dtype=torch.float32)
    model.dropout.eval()
    for package in packages:
        task, state = package["task_id"], package["state_id"]
        n = 2 if (task, state) == ("x", "s") else 1
        for row in rows[package["package_id"]]:
            logits = model(
                torch.tensor([row["input_ids"]]),
                None,
                False,
                torch.tensor(row["target_positions"]) - 1,
            ).logits[0]
            independent = independent + torch.nn.functional.cross_entropy(
                logits, torch.tensor(row["target_ids"]), reduction="sum"
            ) * core.mass(mu[task]) * core.mass(pi[task][state]) / (
                n * package["whole_package_target_tokens"]
            )
    expected = torch.autograd.grad(independent, model.weight)[0]
    assert torch.allclose(actual.G["weight"], expected, atol=1e-7, rtol=1e-6)
    assert torch.equal(model.weight, before) and bool((model.weight.grad == 7).all())
    assert torch.equal(torch.get_rng_state(), rng) and model.training
    pullback = {"weight": torch.arange(9, dtype=torch.float32).reshape(3, 3).square()}
    contribution = actual.centered(pi, mu, pullback)
    assert abs(contribution["C"]["control"]["c"]) < 1e-12
    assert abs(sum(core.mass(pi["x"][s]) * v for s, v in contribution["C"]["x"].items())) < 1e-12
    assert any(abs(v) > 0 for v in contribution["C"]["x"].values())
    assert actual.accounting["packages"] == 4 and actual.accounting["segments"] == 5
    assert actual.accounting["target_tokens"] == 6 and actual.accounting["states"] == 3
