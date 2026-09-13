"""CPU numerical and file-boundary controls, never an actual Student run."""

from types import SimpleNamespace

import pytest
import torch

from trusted_synthesis.experiments.finance_qa_vnext_anchored_vtdo import gradients as g
from trusted_synthesis.experiments.finance_qa_vnext_anchored_vtdo import isolation
from trusted_synthesis.experiments.finance_qa_vnext_anchored_vtdo import protocol as p


class Tiny(torch.nn.Module):
    def __init__(self):
        super().__init__()
        self.theta = torch.nn.Parameter(torch.tensor([0.1, 0.2, -0.1]))
        self.register_buffer("scale", torch.tensor(1.0))
        self.dropout = torch.nn.Dropout(0.4)

    def forward(self, input_ids, attention_mask=None, use_cache=False, logits_to_keep=None):
        logits = self.dropout(self.theta * self.scale)[None, None, :].expand(
            1, input_ids.shape[1], -1
        )
        if isinstance(logits_to_keep, torch.Tensor):
            logits = logits[:, logits_to_keep, :]
        return SimpleNamespace(logits=logits)


def package(identifier, state, target):
    return {
        "package_id": identifier,
        "pool": "A",
        "task_id": "x",
        "state_id": state,
        "role": "train",
        "whole_package_target_tokens": 1,
        "rows": [
            {
                "representation": {
                    "input_ids": [0, target],
                    "target_mask": [0, 1],
                    "labels": [-100, target],
                    "sequence_length": 2,
                    "target_token_count": 1,
                }
            }
        ],
    }


def test_class_gradient_means_and_real_buffers_unchanged():
    model = Tiny()
    model.train()
    model.theta.grad = torch.ones_like(model.theta)
    result = g.class_gradients(
        model, [package("a", "E", 0), package("b", "E", 1), package("c", "M", 2)]
    )
    probability = model.theta.detach().softmax(-1)
    assert torch.allclose(
        result["gradients"]["x"]["E"]["theta"], probability - torch.tensor([0.5, 0.5, 0.0])
    )
    assert torch.allclose(
        result["gradients"]["x"]["M"]["theta"], probability - torch.tensor([0.0, 0.0, 1.0])
    )
    assert torch.equal(model.theta.grad, torch.ones_like(model.theta))
    assert model.training and model.dropout.training
    assert result["artifact"]["forward_backward_rows"] == 3
    assert result["artifact"]["sequence_tokens"] == 6


def test_virtual_forward_uses_new_point_without_mutating_original():
    model = Tiny()
    original = model.theta.detach().clone()
    model.train()
    virtual = g.FunctionalStudent(
        model, {"theta": model.theta.detach() + torch.tensor([0.2, -0.1, 0.3])}
    )
    output = virtual(input_ids=torch.tensor([[0, 1]])).logits
    assert torch.allclose(output[0, 0], original + torch.tensor([0.2, -0.1, 0.3]))
    output.sum().backward()
    assert model.theta.grad is None
    assert next(virtual.parameters()).grad is not None
    assert (
        torch.equal(model.theta, original)
        and model.training
        and virtual.assert_original_unchanged()
    )


def test_virtual_drift_detected():
    model = Tiny()
    virtual = g.FunctionalStudent(model, {"theta": model.theta.detach().clone()})
    with torch.no_grad():
        model.theta.add_(1)
    with pytest.raises(ValueError, match="original_model_changed"):
        virtual.assert_original_unchanged()


@pytest.mark.parametrize("kind", ["duplicate", "heldout", "wrong_L", "mixed_pool"])
def test_invalid_class_gradient_inputs_rejected(kind):
    rows = [package("a", "E", 0), package("b", "M", 1)]
    if kind == "duplicate":
        rows[1]["package_id"] = "a"
    if kind == "heldout":
        rows[1]["role"] = "heldout"
    if kind == "wrong_L":
        rows[1]["whole_package_target_tokens"] = 2
    if kind == "mixed_pool":
        rows[1]["pool"] = "B"
    with pytest.raises(ValueError):
        g.class_gradients(Tiny(), rows)


def test_modes_restored_after_error():
    model = Tiny()
    model.train()
    model.dropout.eval()
    with pytest.raises(RuntimeError), g.evaluation_mode(model):
        assert not model.training
        raise RuntimeError("synthetic")
    assert model.training and not model.dropout.training


@pytest.mark.parametrize(
    "name",
    [
        p.PROTECTED_STUDY + "/scores/confirm/report.json",
        p.PROTECTED_STUDY + "/training/final_adapter.safetensors",
        "other/confirm/result.json",
        "other/confirmation.json",
        "../outside",
    ],
)
def test_forbidden_development_reads_even_if_allowlisted(tmp_path, name):
    reader = isolation.DevelopmentReader(tmp_path, [name])
    with pytest.raises(ValueError):
        reader.read(name)
    assert not reader.accesses


def test_read_allowlist_has_actual_bytes_digest(tmp_path):
    (tmp_path / "public.json").write_bytes(b"public-only")
    reader = isolation.DevelopmentReader(tmp_path, ["public.json"])
    assert reader.read("public.json") == b"public-only"
    assert reader.accesses == [
        {"path": "public.json", "sha256": p.sha(b"public-only"), "bytes": 11}
    ]
    with pytest.raises(ValueError):
        reader.read("undeclared.json")


def test_confirmation_presence_never_opens_outcomes(tmp_path, monkeypatch):
    folder = tmp_path / p.PROTECTED_STUDY / "scores/confirm"
    folder.mkdir(parents=True)
    path = folder / "private_report.json"
    path.write_bytes(b"must not read")
    monkeypatch.setattr(type(path), "read_bytes", lambda *a: pytest.fail("no outcome reads"))
    result = isolation.confirmation_presence(tmp_path)
    assert result["contents_opened"] == 0 and result["absence_proves_never_computed"] is False
    assert next(row for row in result["paths"] if row["relative_path"].endswith("scores/confirm"))[
        "exists"
    ]


@pytest.mark.parametrize(
    "name", [p.PROTECTED_STUDY + "/new.json", "../new", p.OUTPUT, "unrelated/result"]
)
def test_new_outputs_confined_to_new_algorithm(tmp_path, name):
    with pytest.raises(ValueError):
        isolation.new_output(tmp_path, name)


def test_new_budget_never_implicitly_authorizes_GPU():
    assert p.policy()["conditional_total_local_Student_sessions"] == 16740
    assert p.policy()["new_GPU_or_Student_execution_authorized"] is False
    with pytest.raises(ValueError, match="not_authorized"):
        isolation.require_production_authorization()


def test_write_once_and_record_identity(tmp_path):
    path = tmp_path / "one.json"
    value = p.record("test", quantity=1)
    p.write_once(path, value)
    assert p.checked_record(p.read_json(path), "test") == value
    with pytest.raises(FileExistsError):
        p.write_once(path, value)
    with pytest.raises(ValueError):
        p.checked_record({**value, "quantity": 2}, "test")
