import importlib
import sys
from pathlib import Path

import pytest
import torch
from torch import nn

sys.path.insert(0, str(Path(__file__).parents[1] / "scripts"))
saved = importlib.import_module("fixed_kernel_anchored_saved_tensors_20260916")


def test_only_bound_frozen_views_are_retained_with_equal_complete_gradient():
    class Tiny(nn.Module):
        def __init__(self):
            super().__init__()
            self.weight = nn.Parameter(
                torch.arange(16, dtype=torch.float32).reshape(4, 4) / 11, requires_grad=False
            )

        def forward(self, input_ids):
            return input_ids @ self.weight.T + (input_ids @ self.weight.T).square()

    model = Tiny()
    results, reports = [], []
    for retain in (False, True):
        x = torch.ones((2, 4), requires_grad=True)
        store = saved.SavedTensorStore(model, retain_frozen=retain, pin_memory=False)
        with store.context():
            y = model(input_ids=x).sum()
            results.append(torch.autograd.grad(y, x)[0])
        reports.append(store.report())
    assert torch.equal(*results)
    assert reports[0]["save_events"]["frozen_weight_or_view"] == 2
    assert reports[0]["logical_saved_bytes"]["frozen_weight_or_view"] == 128
    assert reports[0]["unique_source_storage_lifetime_bytes"]["frozen_weight_or_view"] == 64
    assert reports[1]["actual_host_allocation_bytes"].get("frozen_weight_or_view", 0) == 0
    assert reports[1]["actual_host_allocation_bytes"]["prefill_activation"] > 0
    assert sum(reports[1]["live_host_bytes_after_response"].values()) == 0


def test_mutated_bound_view_is_rejected_not_reused_by_address():
    model = nn.Linear(3, 3, bias=False)
    model.requires_grad_(False)
    store = saved.SavedTensorStore(model, retain_frozen=True, pin_memory=False)
    packed = store.pack(model.weight.T)
    model.weight.add_(1)
    with pytest.raises(ValueError, match="mutated_before_backward"):
        store.unpack(packed)
