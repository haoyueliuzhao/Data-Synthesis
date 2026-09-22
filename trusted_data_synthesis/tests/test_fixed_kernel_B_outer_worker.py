"""Synthetic CPU restart controls; never open real models, feedback or .pt files."""

import importlib
import sys
from collections import Counter
from pathlib import Path
from types import SimpleNamespace

import pytest
import torch

sys.path.insert(0, str(Path(__file__).parents[1] / "scripts"))
w = importlib.import_module("fixed_kernel_B_outer_worker_20260922")
p = w.p


def digest(values):
    return p.sha(p.encode({name: value.tolist() for name, value in sorted(values.items())}))


def tiny_runtime(tmp_path, *, maximum_extra=128):
    reservations, declarations = [], []
    required = {}
    fail = {"before_commit": None, "after_commit": None}

    def reserve(kind, key, attempt, unit):
        assert kind == "feedback_response"
        marker = (key, attempt, unit)
        assert marker not in reservations
        if sum(row[0] == key for row in reservations) >= required[key] + maximum_extra:
            raise ValueError("synthetic.feedback_replay_budget_exhausted")
        reservations.append(marker)

    def declare(key, count):
        if key in required:
            assert required[key] == count
        required[key] = count
        declarations.append((key, count))

    def atomic(path, value):
        path.parent.mkdir(parents=True, exist_ok=True)
        if fail["before_commit"] == value["cursor"]:
            fail["before_commit"] = None
            raise RuntimeError("injected_before_commit")
        assert not path.exists()
        # All files here contain two-element tensors created by this test.
        torch.save(value, path)
        if fail["after_commit"] == value["cursor"]:
            fail["after_commit"] = None
            raise RuntimeError("injected_after_commit")

    c = SimpleNamespace(
        RAW=tmp_path,
        reserve=reserve,
        set_replay_required=declare,
        capacity_boundary=lambda *args, **kwargs: None,
        emit=lambda _: None,
        s=SimpleNamespace(atomic_torch=atomic),
        old=SimpleNamespace(gate=SimpleNamespace(tensor_digest=digest)),
    )
    return c, reservations, declarations, fail


def responses():
    return [
        dict(trajectory=1 if i < 2 else 5, turn=i % 2, tokens=i + 2, last_in_trajectory=i in (1, 3))
        for i in range(4)
    ]


def gradient_counter(calls):
    def compute(row):
        calls.append(row["tokens"])
        return {"theta": torch.tensor([row["tokens"], -0.25], dtype=torch.float32)}, {
            "cached_forward_target_positions": row["tokens"],
        }

    return compute


def authority():
    return dict(
        job_key="B_delayed_c_11",
        plan_id="frozen",
        prefix_snapshot_id="prefix200",
        inventory_id="saved360",
        required_responses=4,
    )


@pytest.mark.parametrize("failure", ["before_commit", "after_commit"])
def test_response_restart_matches_original_ordered_FP32_sum(tmp_path, failure):
    c, reservations, _, fail = tiny_runtime(tmp_path)
    theta = {"theta": torch.tensor([7.0, 8.0], dtype=torch.float32)}
    fail[failure] = 2
    first_calls, later_calls = [], []
    with pytest.raises(RuntimeError, match="injected"):
        w.replay_responses(
            c,
            tmp_path / "replay",
            authority(),
            theta,
            responses(),
            "attempt1",
            gradient_counter(first_calls),
            0,
        )
    result, accounting = w.replay_responses(
        c,
        tmp_path / "replay",
        authority(),
        theta,
        responses(),
        "attempt2",
        gradient_counter(later_calls),
        0,
    )
    expected = torch.zeros(2, dtype=torch.float32)
    for row in responses():
        expected.add_(torch.tensor([row["tokens"], -0.25], dtype=torch.float32), alpha=1 / 360)
    assert torch.equal(result["theta"], expected)
    assert torch.equal(theta["theta"], torch.tensor([7.0, 8.0]))
    assert accounting == Counter(
        responses_replayed=4,
        sampled_tokens_with_parameter_derivative=14,
        cached_forward_target_positions=14,
        positive_reward_trajectories=2,
    )
    assert later_calls == ([3, 4, 5] if failure == "before_commit" else [4, 5])
    assert len(reservations) == (5 if failure == "before_commit" else 4)
    assert [row[2] for row in reservations[-len(later_calls) :]] == list(
        range(4 - len(later_calls), 4)
    )


def test_completed_accumulator_performs_no_new_reservations_or_replay(tmp_path):
    c, reservations, declarations, _ = tiny_runtime(tmp_path)
    theta = {"theta": torch.zeros(2, dtype=torch.float32)}
    first, _ = w.replay_responses(
        c, tmp_path / "replay", authority(), theta, responses(), "first", gradient_counter([]), 0
    )
    second, _ = w.replay_responses(
        c,
        tmp_path / "replay",
        authority(),
        theta,
        responses(),
        "retry",
        lambda _: pytest.fail("replayed committed response"),
        0,
    )
    assert torch.equal(first["theta"], second["theta"])
    assert len(reservations) == 4 and declarations == [("B_delayed_c_11", 4)] * 2


def test_zero_positive_responses_keep_exact_zero_and_register_zero_budget(tmp_path):
    c, reservations, declarations, _ = tiny_runtime(tmp_path)
    bound = {**authority(), "required_responses": 0}
    total, accounting = w.replay_responses(
        c,
        tmp_path,
        bound,
        {"theta": torch.tensor([2.0, 3.0])},
        [],
        "zero",
        lambda _: pytest.fail("zero-Q replay"),
        0,
    )
    assert torch.equal(total["theta"], torch.zeros(2)) and not accounting
    assert not reservations and declarations == [("B_delayed_c_11", 0)]


def test_response_retry_budget_is_finite_before_replay(tmp_path):
    c, reservations, _, fail = tiny_runtime(tmp_path, maximum_extra=0)
    theta = {"theta": torch.zeros(2, dtype=torch.float32)}
    fail["before_commit"] = 1
    with pytest.raises(RuntimeError):
        w.replay_responses(
            c, tmp_path, authority(), theta, responses(), "crashed", gradient_counter([]), 0
        )
    later_calls = []
    with pytest.raises(ValueError, match="budget_exhausted"):
        w.replay_responses(
            c, tmp_path, authority(), theta, responses(), "retry", gradient_counter(later_calls), 0
        )
    assert len(reservations) == 4 and later_calls == [2, 3, 4]


def test_accumulator_binding_rejects_another_prefix_or_feedback(tmp_path):
    c, _, _, _ = tiny_runtime(tmp_path)
    theta = {"theta": torch.zeros(2, dtype=torch.float32)}
    w.replay_responses(
        c, tmp_path, authority(), theta, responses(), "first", gradient_counter([]), 0
    )
    with pytest.raises(ValueError, match="same_sealed_response_accumulator"):
        w.recover_accumulator(
            c, tmp_path, {**authority(), "prefix_snapshot_id": "another-prefix"}, theta
        )


def test_gap_in_response_checkpoints_is_rejected_without_torch_load(tmp_path, monkeypatch):
    (tmp_path / "0002.pt").touch()
    monkeypatch.setattr(
        w.torch, "load", lambda *args, **kwargs: pytest.fail("loaded a discontinuous checkpoint")
    )
    with pytest.raises(ValueError, match="contiguous_response_checkpoints"):
        w.recover_accumulator(None, tmp_path, authority(), {"theta": torch.zeros(2)})


def test_saved_population_reused_without_loading_cache_or_reserving_pass(tmp_path, monkeypatch):
    monkeypatch.setattr(w, "PACKAGES", 2)
    monkeypatch.setattr(w, "STATES", 1)
    names = {"theta": torch.tensor([1.0, 2.0])}
    lineage = dict(plan_id="plan", job_key="B_delayed_c_11", prefix_snapshot_id="prefix")
    binding = dict(id="B_materials", prior={"task": {"state": "1"}}, mu={"task": "1"})
    authority = dict(
        **lineage,
        material_binding_id=binding["id"],
        pi_sha256=p.sha(p.encode(binding["prior"])),
        optimizer_snapshot_id="prefix",
    )
    saved = dict(
        kind="B_full_population",
        binding=authority,
        keys=(("task", "state"),),
        names=("theta",),
        shapes=(torch.Size([2]),),
        matrix=torch.tensor([[1.0, 2.0]]),
        G={"theta": torch.tensor([1.0, 2.0])},
        accounting=dict(packages=2, states=1),
        G_digest=digest({"theta": torch.tensor([1.0, 2.0])}),
    )
    torch.save(saved, tmp_path / "population.pt")

    def population(keys, names, shapes, matrix, G, accounting):
        return SimpleNamespace(
            keys=keys, names=names, shapes=shapes, matrix=matrix, G=G, accounting=accounting
        )

    c = SimpleNamespace(
        reserve=lambda *args: pytest.fail("reserved another population pass"),
        old=SimpleNamespace(
            classes=SimpleNamespace(
                PopulationGradients=population, validate_support=lambda *args: None
            ),
            gate=SimpleNamespace(tensor_digest=digest),
            trajectory_materials=SimpleNamespace(
                load_pool=lambda *args: pytest.fail("reopened cache")
            ),
        ),
    )
    result = w._population(
        c,
        tmp_path,
        tmp_path,
        {"materials": {"binding": binding}},
        lineage,
        None,
        names,
        SimpleNamespace(snapshot={"id": "prefix"}),
        "retry",
    )
    assert result.accounting == dict(packages=2, states=1)
    assert torch.equal(result.G["theta"], saved["G"]["theta"])


@pytest.mark.parametrize(
    "stage,kind", [("prepare", "B_outer_prepared"), ("replay", "B_completed_outer")]
)
def test_completed_stage_reuses_record_without_loading_GPU_or_population(tmp_path, stage, kind):
    run = w._run(11)
    record = p.record(
        kind,
        plan_id="plan",
        job_key=run["key"],
        complete=True,
        **({"numeric_guard_passed": True} if stage == "replay" else {}),
    )
    filename = "prepare_report.json" if stage == "prepare" else "report.json"
    p.write_once(tmp_path / "outer" / run["key"] / filename, record)
    c = SimpleNamespace(
        RAW=tmp_path,
        read_protocol=lambda _: {"id": "plan"},
        restore_prefix_model=lambda *args: pytest.fail("loaded model for a complete stage"),
        capacity_boundary=lambda *args, **kwargs: pytest.fail("requested GPU for a complete stage"),
    )
    assert getattr(w, "_" + stage)(c, tmp_path, run, "new-attempt", 0) == record


def test_concentration_uses_saved_counts_and_marks_reliability_unmeasured():
    result = w.concentration(
        [
            dict(task_id="t1", source_cluster="cik:1", repeat=1),
            dict(task_id="t1", source_cluster="cik:1", repeat=2),
            dict(task_id="t2", source_cluster="cik:1", repeat=1),
            dict(task_id="t3", source_cluster="cik:2", repeat=2),
        ]
    )
    assert result["positive_unique_tasks"] == 3 and result["positive_unique_CIKs"] == 2
    assert result["largest_task_share"] == 0.5 and result["largest_CIK_share"] == 0.75
    assert result["new_point_cross_repeat_reliability"] == "NOT_MEASURED"
    assert result["extra_gradient_or_feedback_calls"] == 0
