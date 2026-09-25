"""Synthetic CPU evidence only: no real feedback, model or CUDA execution."""

import importlib
import sys
from pathlib import Path
from types import SimpleNamespace

import numpy as np
import pytest
import torch

sys.path.insert(0, str(Path(__file__).parents[1] / "scripts"))
w = importlib.import_module("fixed_kernel_B_direction_reliability_20260926")
p = w.p


def digest(values):
    return p.sha(
        p.encode({name: [str(value.dtype), value.tolist()] for name, value in values.items()})
    )


def runtime(tmp_path, cap=99):
    events, failures = [], {"before": None, "after": None}

    def reserve(kind, key, attempt, unit):
        assert kind == "reliability_response"
        marker = (key, attempt, unit)
        assert marker not in events
        if len(events) >= cap:
            raise ValueError("finite response budget")
        events.append(marker)

    def atomic(path, data):
        if failures["before"] == data["cursor"]:
            failures["before"] = None
            raise RuntimeError("injected before")
        path.parent.mkdir(parents=True, exist_ok=True)
        assert not path.exists()
        torch.save(data, path)
        if failures["after"] == data["cursor"]:
            failures["after"] = None
            raise RuntimeError("injected after")

    common = SimpleNamespace(
        b=SimpleNamespace(old=SimpleNamespace(gate=SimpleNamespace(tensor_digest=digest))),
        s=SimpleNamespace(atomic_torch=atomic),
        capacity_boundary=lambda *args, **kwargs: None,
        reserve=reserve,
    )
    return common, events, failures


def responses():
    return [
        dict(trajectory=3 if i < 3 else 7, last_in_trajectory=i in (2, 3), tokens=i + 1)
        for i in range(4)
    ]


def authority():
    return dict(plan_id="test", job_key="B_direction_reliability_29", required_responses=4)


def gradient(calls):
    values = [1e8, 1.0, -1e8, 3.0]

    def compute(row):
        calls.append(row["tokens"])
        return {"x": torch.tensor([values[row["tokens"] - 1], 0.125])}, {
            "cached_forward_target_positions": row["tokens"],
        }

    return compute


@pytest.mark.parametrize("failure", ["before", "after"])
def test_response_atomic_restart_keeps_FP32_total_FP64_trajectory(tmp_path, failure):
    c, reservations, failures = runtime(tmp_path)
    theta = {"x": torch.zeros(2)}
    failures[failure] = 2
    before, after = [], []
    with pytest.raises(RuntimeError, match="injected"):
        w.replay_responses(c, tmp_path, authority(), theta, responses(), 1, gradient(before), 0)
    total, counts = w.replay_responses(
        c, tmp_path, authority(), theta, responses(), 2, gradient(after), 0
    )
    expected = torch.zeros(2)
    for row in responses():
        value, _ = gradient([])(row)
        expected.add_(value["x"], alpha=1 / 360)
    assert torch.equal(total["x"], expected)
    assert torch.equal(theta["x"], torch.zeros(2))
    trajectory = torch.load(tmp_path / "0003.pt", weights_only=False)["trajectory_cpu"]["x"]
    assert trajectory.dtype == torch.float64 and trajectory.tolist() == [1.0, 0.375]
    assert counts["responses_replayed"] == 4 and counts["positive_reward_trajectories"] == 2
    assert len(reservations) == (5 if failure == "before" else 4)
    assert after == ([2, 3, 4] if failure == "before" else [3, 4])


def test_complete_replay_skips_all_derivatives_and_reservations(tmp_path):
    c, reserved, _ = runtime(tmp_path)
    theta = {"x": torch.zeros(2)}
    first, _ = w.replay_responses(c, tmp_path, authority(), theta, responses(), 1, gradient([]), 0)
    second, _ = w.replay_responses(
        c, tmp_path, authority(), theta, responses(), 2, lambda _: pytest.fail("replayed"), 0
    )
    assert len(reserved) == 4
    assert torch.equal(first["x"], second["x"])


def test_finite_budget_stops_before_uncommitted_derivative(tmp_path):
    c, reservations, _ = runtime(tmp_path, cap=2)
    calls = []
    with pytest.raises(ValueError, match="finite response budget"):
        w.replay_responses(
            c, tmp_path, authority(), {"x": torch.zeros(2)}, responses(), 1, gradient(calls), 0
        )
    assert len(reservations) == len(calls) == 2
    assert (tmp_path / "0002.pt").exists() and not (tmp_path / "0003.pt").exists()


@pytest.mark.parametrize("fault", ["authority", "digest", "gap"])
def test_recovery_rejects_changed_identity_corruption_and_gaps(tmp_path, fault):
    c, _, _ = runtime(tmp_path)
    theta = {"x": torch.zeros(2)}
    w.replay_responses(c, tmp_path, authority(), theta, responses(), 1, gradient([]), 0)
    changed = authority()
    if fault == "authority":
        changed["plan_id"] = "other"
    elif fault == "digest":
        path = tmp_path / "0004.pt"
        data = torch.load(path, weights_only=False)
        data["trajectory_cpu"]["x"][0] += 1
        torch.save(data, path)
    else:
        (tmp_path / "0002.pt").unlink()
    with pytest.raises(ValueError, match="reliability"):
        w.recover(c, tmp_path, changed, theta, responses())


@pytest.mark.parametrize("clip", [None, 0.01])
def test_CPU_linear_projection_reuses_original_actual_Adam_derivative(clip):
    from trusted_synthesis.experiments.finance_qa_vnext_anchored_vtdo import (
        optimizer_pullback as adam,
    )

    parameter = torch.nn.Parameter(torch.tensor([0.4, -0.2, 1.0]))
    optimizer = torch.optim.AdamW([parameter], lr=0.03, betas=(0.9, 0.99), foreach=False)
    for i in range(3):
        parameter.grad = torch.tensor([0.3, -0.7, 0.2 + 0.1 * i])
        optimizer.step()
    bound = adam.bind_adamw({"x": parameter}, optimizer, clip_max_norm=clip)
    G = {"x": torch.tensor([0.2, -0.3, 0.15])}
    vector = torch.tensor([0.4, 0.8, -0.6])
    original = adam.pullback(bound, G, {"x": vector})["a"]["x"]
    coefficients = w.original_linear_coefficients(adam, bound, G, ("x",))
    actual = w.cpu_linear_pullback(coefficients, vector)
    torch.testing.assert_close(actual, original.double(), rtol=1e-5, atol=1e-9)
    assert coefficients["active"] is (clip is not None)
    joined = w.cpu_linear_pullback(coefficients, torch.stack((vector, -2 * vector), dim=1))
    torch.testing.assert_close(joined[:, 0], actual)
    torch.testing.assert_close(joined[:, 1], -2 * actual)
    adam._verify(bound)


def geometry():
    return w.direction.Geometry(
        [("train", "left"), ("train", "right")],
        {"train": {"left": 0.5, "right": 0.5}},
        {"train": {"left": 0.5, "right": 0.5}},
        {"train": 1.0},
        [],
    )


def items():
    return [
        dict(index=0, task_id="a", source_cluster="cik:1", repeat=1),
        dict(index=1, task_id="b", source_cluster="cik:2", repeat=2),
        dict(index=2, task_id="a", source_cluster="cik:1", repeat=2),
    ]


def task_rows():
    return [
        dict(task_id="a", source_cluster="cik:1"),
        dict(task_id="b", source_cluster="cik:2"),
        dict(task_id="zero", source_cluster="cik:3"),
    ]


def test_repeat_fixed180_cross_scoring_and_task_CIK_deletion_keep_zero_terms():
    projected = np.array([[10.0, -3.0, -2.0], [-10.0, 3.0, 2.0]])
    analysis, vectors = w.mechanism_analysis(projected, items(), task_rows(), geometry())
    np.testing.assert_allclose(vectors["repeat1_C"].numpy(), projected[:, 0] / 180)
    np.testing.assert_allclose(vectors["repeat2_C"].numpy(), projected[:, 1:].sum(axis=1) / 180)
    np.testing.assert_allclose(vectors["full_C"].numpy(), projected.sum(axis=1) / 360)
    assert analysis["cross"]["S_1_to_2"] < 0 and analysis["cross"]["S_2_to_1"] < 0
    rows = {row["identifier"]: row for row in analysis["grouped_influence_and_deletion"]["task_id"]}
    assert set(rows) == {"a", "b", "zero"}
    assert rows["zero"]["positive_trajectories"] == 0
    assert rows["zero"]["removed_pi_weighted_TV_change"] == 0
    assert rows["a"]["removed_cross_interpretable"] is False
    assert rows["a"]["fixed_full_denominator"] == 360
    assert rows["a"]["fixed_half_denominator"] == 180
    assert analysis["not_a_stage2_selection_gate"]
    assert analysis["no_seed_or_task_selection_authorized"]


def test_empty_half_is_not_regrouped_or_mistaken_for_confirmation():
    positive = [items()[0]]
    analysis, _ = w.mechanism_analysis(np.array([[1.0], [-1.0]]), positive, task_rows(), geometry())
    assert analysis["cross"]["interpretable"] is False
    assert analysis["cross"]["S_1_to_2"] is None
    assert analysis["halves"]["2"]["status"] == "UNINFORMATIVE_ZERO_HALF"
    assert analysis["halves"]["2"]["denominator"] == 180


def test_equivalence_requires_both_registered_numeric_limits():
    geo = geometry()
    C = np.array([0.01, -0.01])
    proposal, _ = geo.propose(C, "c_only_anchored", 1)
    reference = geo.nested(C)
    assert w.equivalence(geo, C, reference, geo.nested(proposal), 1)["passed"]
    assert not w.equivalence(geo, -C, reference, geo.nested(proposal), 1)["passed"]
    # C is identical, but a mismatched distribution still fails its independent gate.
    assert not w.equivalence(geo, C, reference, geo.pi, 1)["passed"]


def test_saved_gJ_comparison_does_not_ignore_projection_nullspace():
    reference = {"x": torch.tensor([1.0, 2.0, 0.0])}
    equal = w.gradient_equivalence(reference, reference)
    assert equal["passed"] and equal["bitwise_equal"] and equal["relative_L2"] == 0
    # The last coordinate could be invisible to C, but it is checked directly.
    changed = {"x": torch.tensor([1.0, 2.0, 0.01])}
    result = w.gradient_equivalence(changed, reference)
    assert not result["passed"] and result["maximum_absolute_error"] > 0.009
    assert result["relative_L2"] > 0


def test_saved_population_loader_never_falls_back_to_new_G(tmp_path):
    parent = {"materials": {"binding": {"id": "binding", "prior": {}}}}
    c = SimpleNamespace(b=SimpleNamespace(old=SimpleNamespace()))
    with pytest.raises(FileNotFoundError):
        w.load_original_population(
            c, tmp_path / "absent.pt", parent, {}, SimpleNamespace(snapshot={"id": "snapshot"}), {}
        )


def test_zero_positives_have_zero_vectors_and_no_response_work(tmp_path):
    c, reservations, _ = runtime(tmp_path)
    total, counts = w.replay_responses(
        c,
        tmp_path,
        {**authority(), "required_responses": 0},
        {"x": torch.zeros(2)},
        [],
        1,
        lambda _: pytest.fail("zero replay"),
        0,
    )
    assert torch.equal(total["x"], torch.zeros(2)) and not counts and not reservations
    analysis, _ = w.mechanism_analysis(np.empty((2, 0)), [], task_rows(), geometry())
    assert analysis["cross"]["interpretable"] is False
    assert analysis["full_weighted_pi_TV"] == 0


def test_projection_reads_only_complete_trajectory_end_checkpoints(tmp_path):
    c, _, _ = runtime(tmp_path)
    theta = {"x": torch.zeros(2)}
    w.replay_responses(c, tmp_path, authority(), theta, responses(), 1, gradient([]), 0)
    population = SimpleNamespace(names=("x",), keys=geometry().keys, matrix=torch.eye(2))
    coefficients = dict(
        diagonal=torch.ones(2, dtype=torch.float64),
        G=torch.ones(2, dtype=torch.float64),
        norm=1.0,
        coefficient=1.0,
        active=False,
        epsilon=1e-6,
    )
    positive = [dict(index=3), dict(index=7)]
    previous_threads = torch.get_num_threads()
    actual = w.project_trajectories(
        c, tmp_path, authority(), responses(), positive, population, coefficients, geometry()
    )
    expected = geometry().centered(np.array([[-1.0, -3.0], [-0.375, -0.125]]))
    np.testing.assert_allclose(actual, expected)
    assert torch.get_num_threads() == previous_threads


def test_completed_report_reused_before_original_input_or_model_reload(tmp_path):
    directory = tmp_path / "reliability/B_direction_reliability_29"
    directory.mkdir(parents=True)
    report = p.record("B_direction_reliability_report", plan_id="test", seed=29, complete=True)
    (directory / "report.json").write_bytes(p.encode(report))
    c = SimpleNamespace(
        RAW=tmp_path, read_protocol=lambda _: {"id": "test"}, b=SimpleNamespace(old=None)
    )
    assert w._run(c, Path("."), 29, 5, 0) == report
