import importlib
import sys
from pathlib import Path

import torch
from torch import nn

sys.path.insert(0, str(Path(__file__).parents[1] / "scripts"))
canonical = importlib.import_module("fixed_kernel_anchored_canonical_saves_20260916")


def test_repeated_bound_transpose_has_one_shared_native_contiguous_layout():
    layer = nn.Linear(3, 5, bias=False).requires_grad_(False)
    store = canonical.CanonicalSavedTensorStore(layer, pin_memory=False)
    view = layer.weight.T
    first, second = store.pack(view), store.pack(view)
    assert first.value is second.value
    assert first.value.is_contiguous() and not view.is_contiguous()
    assert torch.equal(first.value, view)
    assert store.bank.extra_bytes == view.numel() * view.element_size()
    assert torch.equal(store.unpack(first), view)
