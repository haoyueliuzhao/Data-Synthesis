"""Instrumented no-training, all-parameter and phase-boundary controls on CPU."""

from pathlib import Path

import pytest
import torch

from trusted_synthesis.domains.finance.qa_vnext.runtime import DurableStore
from trusted_synthesis.experiments.finance_qa_vnext_pq_response_diagnostic import (
    guards,
    plan,
    stage,
)


def test_all_parameter_fingerprint_covers_base_and_adapter_like_parameters():
    model = (
        torch.nn.Sequential(torch.nn.Linear(2, 2), torch.nn.Linear(2, 1))
        .eval()
        .requires_grad_(False)
    )
    before = guards.parameter_fingerprint(model, chunk_bytes=3)
    with guards.inference_only() as calls:
        model(torch.ones(1, 2))
    guards.assert_unchanged(before, guards.parameter_fingerprint(model, chunk_bytes=3))
    assert not any(calls.values())
    assert before["parameter_count"] == 9 and before["named_tensors"] == 4
    with torch.no_grad():
        model[0].weight[0, 0] += 1
    with pytest.raises(ValueError, match="parameter_bytes_or_versions"):
        guards.assert_unchanged(before, guards.parameter_fingerprint(model))


def test_mutate_restore_detected_by_parameter_version():
    model = torch.nn.Linear(2, 2).eval().requires_grad_(False)
    before = guards.parameter_fingerprint(model)
    old = model.weight.clone()
    with torch.no_grad():
        model.weight.add_(1)
        model.weight.copy_(old)
    after = guards.parameter_fingerprint(model)
    assert before["sha256"] == after["sha256"]
    with pytest.raises(ValueError):
        guards.assert_unchanged(before, after)


@pytest.mark.parametrize(
    "action", ["optimizer", "tensor_backward", "autograd_backward", "autograd_grad", "train"]
)
def test_training_entry_points_forbidden(action):
    model = torch.nn.Linear(1, 1).eval()
    with guards.inference_only() as calls, pytest.raises(RuntimeError, match="inference_only"):
        if action == "optimizer":
            torch.optim.SGD(model.parameters(), lr=0.1)
        elif action == "tensor_backward":
            torch.tensor(1.0).backward()
        elif action == "autograd_backward":
            torch.autograd.backward(torch.tensor(1.0))
        elif action == "autograd_grad":
            torch.autograd.grad(torch.tensor(1.0), torch.tensor(1.0))
        else:
            model.train()
    assert sum(calls.values()) == 1


@pytest.mark.parametrize(
    "relative",
    [
        plan.OUTPUT + "/scoring/P_11/report.json",
        plan.OUTPUT + "/preparation/private/L1.json",
        plan.OUTPUT + "/preparation/weight_view.json",
        plan.PARENT + "/training/P_11/report.json",
        plan.PARENT + "/evaluation/P_11/sessions/T1/result.json",
        plan.SOURCE + "/closeout/materialization/positive/T_L1_03/000.tokens.json",
    ],
)
def test_generation_cannot_read_scores_targets_gold_or_other_outputs(tmp_path, relative):
    path = tmp_path / relative
    path.parent.mkdir(parents=True)
    path.write_text("synthetic forbidden")
    with guards.artifact_guard(tmp_path, "generation", "P_11") as (counts, _):
        with pytest.raises(PermissionError, match="forbidden_phase_artifact"):
            path.read_text()
    assert counts["cross_phase_artifact_access"] == 1


def test_scorer_cannot_read_generation(tmp_path):
    with guards.artifact_guard(tmp_path, "scoring", "B0"):
        with pytest.raises(PermissionError):
            (tmp_path / plan.OUTPUT / "generation/P_11/report.json").read_bytes()


def test_phase_can_durably_create_own_output_with_directory_sync(tmp_path):
    with guards.artifact_guard(tmp_path, "generation", "P_11") as (counts, network):
        store = DurableStore(tmp_path / plan.OUTPUT / "generation/P_11")
        store.json("synthetic.json", {"not_model_output": True})
    assert not any(counts.values()) and not any(network.values())


def test_bound_token_arrays_load_under_scoring_boundary_without_tokenizer():
    from trusted_synthesis.experiments.finance_qa_vnext_pq_student.weights import load_rows

    root = Path(__file__).resolve().parents[2]
    view = plan.read_json(root / plan.PARENT / "preparation/weight_view.json")
    with guards.artifact_guard(root, "scoring", "B0") as (calls, _):
        rows = load_rows(root, view)
    assert len(rows) == 36 and not any(calls.values())


def test_worker_environment_does_not_inherit_scores_or_credentials(monkeypatch):
    monkeypatch.setenv("DEEPSEEK_API_KEY", "synthetic")
    monkeypatch.setenv("SCORE_JSON", "synthetic")
    env = stage.worker_environment(Path("/tmp"), 3)
    assert "DEEPSEEK_API_KEY" not in env and "SCORE_JSON" not in env
    assert env["CUDA_VISIBLE_DEVICES"] == "3" and env["HF_HUB_OFFLINE"] == "1"


def test_generation_module_does_not_import_scorer_or_private_evaluator():
    import ast

    source = (
        Path(__file__).resolve().parents[1]
        / "src/trusted_synthesis/experiments/finance_qa_vnext_pq_response_diagnostic/generation.py"
    )
    imports = [
        node.module or ""
        for node in ast.walk(ast.parse(source.read_text()))
        if isinstance(node, ast.ImportFrom)
    ]
    assert not any(
        any(word in module for word in (".analysis", ".scoring", ".stage", ".evaluate"))
        for module in imports
    )


def test_GPU_admission_filters_busy_devices(monkeypatch):
    monkeypatch.setattr(
        stage.subprocess,
        "check_output",
        lambda *a, **k: (
            "0, NVIDIA A100-SXM4-80GB, 81154\n1, NVIDIA A100-SXM4-80GB, 16000\n"
            "2, NVIDIA A100-SXM4-40GB, 75000\n9, NVIDIA A100-SXM4-80GB, 81154\n"
        ),
    )
    assert stage.available_devices() == [0]


def test_fixed_queue_order_and_failed_worker_never_retried(tmp_path, monkeypatch):
    monkeypatch.setattr(stage, "available_devices", lambda: [0])
    monkeypatch.setattr(stage.time, "sleep", lambda _: None)
    started = []

    class Process:
        pid = 1

        def poll(self):
            return 1

    def launch(root, phase, variant, gpu):
        started.append((phase, variant))
        return Process()

    monkeypatch.setattr(stage, "launch", launch)
    store = DurableStore(tmp_path / "execution")
    with pytest.raises(ValueError, match="phase_incomplete"):
        stage.run_queue(tmp_path, "scoring", plan.VARIANTS, store)
    assert started == [("scoring", "B0")]
