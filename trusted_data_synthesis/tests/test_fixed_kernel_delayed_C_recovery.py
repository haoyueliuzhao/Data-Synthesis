"""Only checkpoint/recovery contracts; no additional model generation or GPU trials."""

import copy
import importlib
import sys
from pathlib import Path

import pytest
import torch

sys.path.insert(0, str(Path(__file__).parents[1] / "scripts"))
s = importlib.import_module("fixed_kernel_delayed_C_recovery_state_20260921")
r = importlib.import_module("run_fixed_kernel_delayed_C_recovery_20260921")


def model_and_optimizer():
    model = torch.nn.Sequential(torch.nn.Linear(3, 2), torch.nn.Dropout(0.25))
    optimizer = torch.optim.AdamW(model.parameters(), lr=1e-4, weight_decay=0.0)
    return model, optimizer


def one_step(model, optimizer):
    optimizer.zero_grad(set_to_none=True)
    loss = model(torch.ones(2, 3)).square().sum()
    loss.backward()
    torch.nn.utils.clip_grad_norm_(model.parameters(), 1.0)
    optimizer.step()
    return loss.detach()


def test_optimizer_and_rng_restore_reproduce_next_dropout_update():
    torch.manual_seed(29)
    first, optimizer = model_and_optimizer()
    one_step(first, optimizer)
    names = dict(first.named_parameters())
    bound = s.old.adam.bind_adamw(names, optimizer, clip_max_norm=1.0)
    state = {}
    for row in bound.parameters:
        for prefix, value in (
            ("theta", row.theta),
            ("first_moment", row.first),
            ("second_moment", row.second),
        ):
            state[prefix + "/" + row.name] = value.clone()
    rng = s.capture_rng(1, cuda=False)
    expected_loss = one_step(first, optimizer)
    wanted = s.old.adam.bind_adamw(names, optimizer, clip_max_norm=1.0).snapshot
    second, resumed = model_and_optimizer()
    s.restore_optimizer(dict(second.named_parameters()), resumed, state, bound.snapshot, step=1)
    s.restore_rng(rng, cuda=False)
    assert torch.equal(one_step(second, resumed), expected_loss)
    assert (
        s.old.adam.bind_adamw(dict(second.named_parameters()), resumed, clip_max_norm=1.0).snapshot
        == wanted
    )
    state["theta/0.weight"][0, 0] += 1
    with pytest.raises(ValueError, match="exact_saved_parameter"):
        s.check_saved_state(state, bound.snapshot, 1)


def test_atomic_checkpoint_never_overwrites_existing_state(tmp_path):
    path = tmp_path / "0201.pt"
    s.atomic_torch(path, {"cursor": 201, "value": torch.tensor([2.0])})
    assert torch.load(path, weights_only=True)["cursor"] == 201
    assert not list(tmp_path.glob("*.partial.*"))
    with pytest.raises(ValueError, match="no_checkpoint_overwrite"):
        s.atomic_torch(path, {"cursor": 202})
    assert torch.load(path, weights_only=True)["cursor"] == 201


def test_replay_gate_rejects_a_changed_dropout_or_gradient_path():
    original = dict(
        id="update",
        tasks=["t"],
        packages=["p"],
        target_tokens=3,
        sequence_tokens=5,
        optimizer_step_calls=1,
        physical_package_count=1,
        packages_completed=1,
        rows_completed=1,
        loss_rule="same",
        weighted_loss=0.2,
        preclip_gradient_norm=0.4,
        package_losses=[dict(package_id="p", target_tokens=3, target_nll_sum=2.0)],
    )
    assert s.compare_replayed_update(original, original)["exact_report_id"]
    changed = copy.deepcopy(original)
    changed["package_losses"][0]["target_nll_sum"] += 0.001
    with pytest.raises(ValueError, match="replayed_loss_or_gradient_mismatch"):
        s.compare_replayed_update(changed, original)


def test_recovery_budget_records_repeated_compute_without_new_feedback():
    budget = s.recovery_budget({11: 400, 29: 200, 47: 303})
    assert budget["cumulative_completed_optimizer_updates"] == 1303
    assert budget["effective_final_optimizer_updates"] == 1200
    assert budget["repeated_completed_optimizer_updates"] == 103
    assert budget["new_feedback_sessions"] == budget["new_private_feedback_scores"] == 0
    assert budget["new_final_greedy_sessions"] == 360
    with pytest.raises(ValueError, match="fixed_failed_attempt_inventory"):
        s.recovery_budget({11: 400, 29: 200, 47: 304})


def test_one_worker_failure_does_not_terminate_the_other(monkeypatch, tmp_path):
    plan = {
        "runs": [{"key": "broken"}, {"key": "healthy"}],
        "budget": {"maximum_resource_failures_per_run": 3},
    }
    monkeypatch.setattr(r, "plans", lambda root: (plan, {}))
    monkeypatch.setattr(r.old, "host_memory", lambda: {"MemAvailable_bytes": 2**40})
    monkeypatch.setattr(r.time, "sleep", lambda _: None)
    monkeypatch.setattr(r.d.audit, "publish", lambda *args: None)
    monkeypatch.setattr(
        r, "publish_final", lambda *args: pytest.fail("incomplete matrix published")
    )

    class Lease:
        def close(self):
            pass

        def fileno(self):
            return 0

    monkeypatch.setattr(
        r.old,
        "claim_gpus",
        lambda *args, **kwargs: [({"uuid": str(i), "index": i}, Lease()) for i in (0, 1)],
    )

    class Process:
        pid = 1

        def __init__(self, command, **kwargs):
            self.key = command[command.index("--run") + 1]
            self.count = 0

        def poll(self):
            self.count += 1
            if self.key == "broken":
                return 1
            if self.count == 1:
                return None
            r.p.write_once(tmp_path / r.OUTPUT / "runs/healthy/report.json", {"completed": True})
            return 0

        def terminate(self):
            pytest.fail("healthy worker terminated")

    monkeypatch.setattr(r.subprocess, "Popen", Process)
    r.coordinate(tmp_path)
    result = r.p.read_json(tmp_path / r.OUTPUT / "coordinator_failure.json")
    assert result["healthy_workers_not_killed"]
    assert set(result["failed"]) == {"broken"}
    assert (tmp_path / r.OUTPUT / "runs/healthy/report.json").exists()
