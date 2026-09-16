"""One CPU control for the new checkpoint/functional-call backward boundary."""

import importlib
import sys
from pathlib import Path
from types import SimpleNamespace

import torch
from torch import nn
from torch.utils.checkpoint import checkpoint

sys.path.insert(0, str(Path(__file__).parents[1] / "scripts"))
gate = importlib.import_module("fixed_kernel_anchored_sources_gpu_gate_20260916")


def test_checkpoint_backward_uses_virtual_parameters_and_restores_real_model():
    class Tiny(nn.Module):
        def __init__(self):
            super().__init__()
            self.weight = nn.Parameter(torch.arange(16, dtype=torch.float32).reshape(4, 4) / 13)
            self.drop = nn.Dropout(0.05)

        def forward(self, input_ids, attention_mask, use_cache, logits_to_keep):
            values = torch.nn.functional.one_hot(input_ids, num_classes=4).float()

            def hidden(x):
                return torch.tanh(self.drop(x) @ self.weight).square()

            result = (
                checkpoint(hidden, values, use_reentrant=False) if self.training else hidden(values)
            )
            return SimpleNamespace(logits=result[:, logits_to_keep, :])

    model = Tiny()
    original = model.weight.detach().clone()
    virtual = {"weight": (original + 0.4).requires_grad_(True)}
    actual, grads = gate.replay_logp(model, virtual, [0, 1], [2, 3])
    reference = virtual["weight"].detach().clone().requires_grad_(True)
    values = torch.nn.functional.one_hot(torch.tensor([1, 2]), num_classes=4).float()
    logits = torch.tanh(values @ reference).square()
    logps = torch.log_softmax(logits, -1).gather(-1, torch.tensor([[2], [3]])).squeeze(-1)
    expected = torch.autograd.grad(logps.sum(), reference)[0]
    assert torch.allclose(actual, logps.detach())
    assert torch.allclose(grads["weight"], expected)
    assert torch.equal(model.weight, original) and model.weight.grad is None
    assert model.training and model.drop.training and model.drop.p == 0.05
