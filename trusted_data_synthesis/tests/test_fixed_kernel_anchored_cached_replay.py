"""A differentiable-cache control: prefix parameter derivatives must not detach."""

import importlib
import sys
from pathlib import Path
from types import SimpleNamespace

import torch
from torch import nn

sys.path.insert(0, str(Path(__file__).parents[1] / "scripts"))
replay = importlib.import_module("fixed_kernel_anchored_sources_cached_replay_20260916")


def test_cached_replay_matches_full_prefix_derivative_and_restores_real_weights():
    class Tiny(nn.Module):
        def __init__(self):
            super().__init__()
            self.weight = nn.Parameter(torch.arange(16, dtype=torch.float32).reshape(4, 4) / 20)
            self.drop = nn.Dropout(0.05)

        def forward(self, input_ids, attention_mask, use_cache, past_key_values, logits_to_keep):
            state = torch.zeros(4) if past_key_values is None else past_key_values
            for token in input_ids[0]:
                state = torch.tanh(state + self.drop(self.weight[token]))
            return SimpleNamespace(
                logits=(state @ self.weight)[None, None, :], past_key_values=state
            )

    model = Tiny()
    before = model.weight.detach().clone()
    theta = {"weight": (before + 0.1).requires_grad_(True)}
    logps, gradient = replay.cached_logp(model, theta, [0, 1], [2, 3], offload=False)
    independent = theta["weight"].detach().clone().requires_grad_(True)
    state = torch.zeros(4)
    expected = []
    for position, token in enumerate([0, 1, 2]):
        state = torch.tanh(state + independent[token])
        if position > 0:
            expected.append(torch.log_softmax(state @ independent, -1)[position + 1])
    expected = torch.stack(expected)
    expected_gradient = torch.autograd.grad(expected.sum(), independent)[0]
    assert torch.allclose(logps, expected.detach(), atol=1e-7)
    assert torch.allclose(gradient["weight"], expected_gradient, atol=1e-7)
    assert bool(gradient["weight"][0].abs().sum() > 0)
    assert torch.equal(model.weight, before) and model.weight.grad is None
    assert model.training and model.drop.training
