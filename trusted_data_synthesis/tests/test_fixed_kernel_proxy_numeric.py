"""Only the new stable reference: cold/zero and nonempty global-clip controls."""

import importlib
import sys
from pathlib import Path

import torch

sys.path.insert(0, str(Path(__file__).parents[1] / "scripts"))
n = importlib.import_module("fixed_kernel_proxy_numeric_20260919")
GROUP = dict(beta1=0.9, beta2=0.999, eps=1e-8, lr=1e-4, maximize=False)


def test_cold_and_zero_same_representable_input():
    h = torch.tensor([0, 0.1, 1e-8, -1e-5], dtype=torch.float32).double()
    result = n.local_diagonal(h, torch.zeros_like(h), torch.zeros_like(h), 0, GROUP, stable=True)
    exact = GROUP["lr"] * GROUP["eps"] / (h.abs() + GROUP["eps"]).square()
    torch.testing.assert_close(result, exact, rtol=1e-12, atol=0)
    assert bool((result > 0).all())


def test_nonempty_negative_and_complete_clip_vjp():
    h = torch.tensor([2.0], dtype=torch.float64)
    first, second = torch.full_like(h, 0.01), torch.full_like(h, 0.0001)
    assert n.local_diagonal(h, first, second, 200, GROUP, stable=True).item() < 0
    g = torch.tensor([0.5, -0.3, 0.4], dtype=torch.float64, requires_grad=True)
    m = torch.tensor([0.01, -0.02, 0.005], dtype=torch.float64)
    v = torch.tensor([0.001, 0.002, 0.0005], dtype=torch.float64)
    covector = torch.tensor([0.2, -0.7, 0.9], dtype=torch.float64)
    step, limit = 200, 0.2
    clipped = g * torch.clamp(limit / (g.norm() + 1e-6), max=1)
    mn = GROUP["beta1"] * m + (1 - GROUP["beta1"]) * clipped
    vn = GROUP["beta2"] * v + (1 - GROUP["beta2"]) * clipped.square()
    update = (
        GROUP["lr"]
        * (mn / (1 - GROUP["beta1"] ** (step + 1)))
        / ((vn / (1 - GROUP["beta2"] ** (step + 1))).sqrt() + GROUP["eps"])
    )
    expected = torch.autograd.grad((update * covector).sum(), g)[0]
    blocks = [dict(start=0, stop=3, shape=[3], step=step, group=0)]
    actual, info = n.pullback(
        g, m, v, covector, blocks, [GROUP], dict(max_norm=limit, epsilon=1e-6)
    )
    torch.testing.assert_close(actual, expected, rtol=1e-11, atol=1e-16)
    assert info["active"]
