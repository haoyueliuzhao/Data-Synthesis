"""New timing/budget controls only; no pilot training or additional feedback."""

import importlib
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest
import torch

sys.path.insert(0, str(Path(__file__).parents[1] / "scripts"))
d = importlib.import_module("run_fixed_kernel_delayed_C_20260919")


def test_only_step200_has_distribution_update():
    assert [step for step in range(400) if d.is_distribution_step(step)] == [200]


def test_new_registration_keeps_three_fresh_paired_runs_and_budget():
    keys = (
        "assets",
        "trajectory_cache",
        "initial_adapter_digests",
        "schedules",
        "training_groups",
        "source_manifest_id",
        "tasks",
        "private_scoring_source_root",
        "runtime_binding",
        "training_configuration",
        "binding_id",
    )
    parent = {key: {"sentinel": key} for key in keys}
    parent["id"] = "parent"
    result = d.registration(parent, "audit")
    assert [r["seed"] for r in result["runs"]] == [11, 29, 47]
    assert result["outer_steps"] == [200] and result["real_updates_per_run"] == 400
    assert result["new_sessions_total"] == 1620 and result["new_generate_cap"] == 51840
    assert result["new_optimizer_updates"] == 1200 and result["no_old_checkpoint_or_RNG_resume"]
    assert (
        result["old_Adam_expression_preserved"]
        and result["primary_comparison"] == "Delayed-C minus Static"
    )
    assert (
        result["SFT_sequence_tokens"] == 538268970
        and result["extra_class_sequence_tokens"] == 53826897
    )
    assert all(result[key] == parent[key] for key in keys)
    result["assets"]["sentinel"] = "changed"
    assert parent["assets"]["sentinel"] == "assets"


def test_worker_cannot_load_model_before_numeric_admission(monkeypatch, tmp_path):
    monkeypatch.setattr(d.p, "read_json", lambda path: {})
    monkeypatch.setattr(d.p, "checked", lambda value, kind: value)
    monkeypatch.setattr(d, "get_admission", lambda root, plan: None)

    def forbidden(*args, **kwargs):
        raise AssertionError("model loading before admission")

    monkeypatch.setattr(d.old.trajectory_training, "load_registered_student", forbidden)
    with pytest.raises(ValueError, match="no_worker_before_audit_gate"):
        d.worker(tmp_path, "A_delayed_c_11")


def test_new_point_guard_compares_C_and_pi_without_switching_formula():
    pi = {"x": {"a": 0.5, "b": 0.5}}
    G = torch.tensor([0.5, 0.5])
    first, second = torch.tensor([0.01, -0.02]), torch.tensor([0.003, 0.004])
    group = dict(beta1=0.9, beta2=0.999, lr=1e-4, eps=1e-8, maximize=False)
    blocks = [dict(start=0, stop=2, shape=[2], step=200, group=0)]
    gJ = {"w": torch.tensor([1.0, -0.25])}
    a, _ = d.numeric.pullback(
        G,
        first,
        second,
        -gJ["w"],
        blocks,
        [group],
        dict(max_norm=1.0, epsilon=1e-6),
        stable=False,
        dtype=torch.float32,
    )
    geometry = d.direction.Geometry([("x", "a"), ("x", "b")], pi, pi, {"x": 1.0}, [])
    C = geometry.centered(a.double().numpy())
    proposed, _ = geometry.propose(C, "c_only_anchored", 1)
    bound = SimpleNamespace(
        parameters=[
            SimpleNamespace(
                name="w", theta=torch.zeros(2), first=first, second=second, step=200, group=0
            )
        ],
        groups=[group],
        clip_max_norm=1.0,
        clip_epsilon=1e-6,
    )
    population = SimpleNamespace(G={"w": G}, matrix=torch.eye(2), keys=geometry.keys)
    result = d.new_point_numeric_guard(
        population,
        bound,
        gJ,
        {"w": a},
        geometry.nested(C),
        {"pi_next": geometry.nested(proposed)},
        pi,
        dict(prior=pi, mu={"x": 1.0}, control_tasks=[]),
        1,
        dict(relative_weighted_C_RMS=1e-3, weighted_pi_TV=1e-5),
    )
    assert result["passed"] and result["reference_not_substituted"]
    assert result["original_Adam_used_for_actual_update"] and result["step"] == 200
