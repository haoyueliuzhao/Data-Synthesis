"""Necessary CPU controls for fixed-q training and same-parent admission.

The tiny fixtures are explicitly not FinQA scientific results or GPU evidence.
"""

import copy
import json
from pathlib import Path
from types import SimpleNamespace

import pytest
import torch

import finqa_v54_training as training
import finqa_v54_worker as worker
from trusted_synthesis.finance_research import v8_training_driver as v8


class TinyStudent(torch.nn.Module):
    def __init__(self):
        super().__init__()
        self.weight = torch.nn.Parameter(torch.arange(20, dtype=torch.float32).reshape(4, 5) / 20)
        self.dropout = torch.nn.Dropout(0.05)

    def forward(self, input_ids, attention_mask, use_cache, logits_to_keep):
        return SimpleNamespace(logits=self.dropout(self.weight[input_ids])[:, logits_to_keep])


def tiny_driver(path, material=None, schedule=None):
    if material is None:
        tasks = [f"t{i}" for i in range(5)]
        packages, rows, chi = [], {}, {}
        for task in tasks:
            chi[task] = {"a": 0, "b": 1}
            for state in ("a", "b"):
                key = task + "/" + state
                packages.append(dict(package_id=key, task_id=task, state_id=state,
                                     whole_package_target_tokens=1, fused=False))
                rows[key] = [dict(input_ids=[0, 1], target_positions=[1],
                                  target_ids=[1 if state == "a" else 2])]
        material = v8.tiny_cpu_pool(tasks, packages, rows, chi=chi)
        body = dict(batches=[dict(step=i + 1, task_ids=tasks) for i in range(894)])
        schedule = {**body, "schedule_sha256": v8.digest(body)}
    model = TinyStudent()
    optimizer = torch.optim.AdamW(model.parameters(), lr=1e-4, weight_decay=0)
    driver = v8.TrainingDriver(model, optimizer, material, root=path, seed=137,
                               arm="C-only", cpu_control_schedule=schedule)
    driver.execution_plan = {"CPU_fixture_only": True}
    return driver


@pytest.fixture
def toy_parent(tmp_path, monkeypatch):
    old_threads = torch.get_num_threads()
    torch.set_num_threads(1)
    driver = tiny_driver(tmp_path / "historical")
    torch.manual_seed(731)
    driver.step()
    driver.step_index, driver.outer_done = 596, [298]
    for value in driver.optimizer.state.values():
        value["step"].fill_(596)
    driver.pi = {task: {"a": 0.4, "b": 0.6} for task in driver.pool.task_ids}
    path = driver.commit("step", dict(CPU_fixture_only=True))
    parent = dict(id="toy-parent", seed=137,
                  parent_checkpoint=training.checkpoint_ref(path),
                  parent_state_digest=v8._tree_digest(driver._payload()),
                  parent_pi=copy.deepcopy(driver.pi),
                  component_digests={"rng": v8._tree_digest(v8._rng())},
                  scientific_sources={"driver": training.file_ref(v8.__file__)})
    monkeypatch.setattr(training, "checked_parent", lambda root, seed: parent)
    yield SimpleNamespace(root=tmp_path / "new", old=driver, parent=parent,
                          rt=SimpleNamespace(torch=torch, v8=v8),
                          monitor=SimpleNamespace(check_stop=lambda *a, **k: None,
                                                  clear_unused=lambda *a, **k: None))
    torch.set_num_threads(old_threads)


def test_real_fixed_q_window_keeps_dropout_adam_rng_and_stops_before_outer(toy_parent):
    f = toy_parent
    driver = tiny_driver(training.branch_root(f.root, 137, "Hold") / "training",
                         f.old.pool, f.old.schedule)
    original_step = type(driver).step
    result = training.execute_training(f.root, 137, "Hold", "protocol", driver,
                                       f.parent["parent_pi"], rt=f.rt, monitor=f.monitor,
                                       distribution_source={"field": "parent.pi"})
    assert type(driver).step is original_step is v8.TrainingDriver.step
    assert driver.step_index == 894 and driver.outer_done == [298]
    assert driver.model.training and driver.model.dropout.p == 0.05
    assert driver.pi == f.parent["parent_pi"]
    assert driver.optimizer.state[driver.model.weight]["step"].item() == 894
    assert result["optimizer_updates"] == result["new_optimizer_updates"] == 298
    assert set(result["snapshots"]) == {"745", "894"}
    assert not list(driver.root.glob("*_outer"))
    assert training.checked_branch_result(f.root, 137, "Hold")["status"] == "COMPLETE"
    with pytest.raises(ValueError, match="completed branch"):
        training.execute_training(f.root, 137, "Hold", "protocol", driver,
                                  f.parent["parent_pi"], rt=f.rt, monitor=f.monitor,
                                  distribution_source={"field": "parent.pi"})


def test_cold_restore_after_actual_commit_never_repeats_that_update(toy_parent):
    f = toy_parent
    q = {task: {"a": 0.7, "b": 0.3} for task in f.old.pool.task_ids}
    root = training.branch_root(f.root, 137, "C05") / "training"
    first = tiny_driver(root, f.old.pool, f.old.schedule)
    observations = []

    def pause(label):
        observations.append(first.step_index)
        if first.step_index == 600:
            raise RuntimeError("CPU explicit stop after durable step600")

    monitor = SimpleNamespace(check_stop=lambda *a, **k: None, clear_unused=pause)
    with pytest.raises(RuntimeError, match="durable step600"):
        training.execute_training(f.root, 137, "C05", "protocol", first, q,
                                  rt=f.rt, monitor=monitor, distribution_source={"condition": "T05"})
    receipt_before = training.sha(root / "step0600_step/state.pt")
    resumed = tiny_driver(root, f.old.pool, f.old.schedule)
    result = training.execute_training(f.root, 137, "C05", "protocol", resumed, q,
                                       rt=f.rt, monitor=f.monitor,
                                       distribution_source={"condition": "T05"})
    assert result["updates_in_final_worker"] == 294
    assert training.sha(root / "step0600_step/state.pt") == receipt_before
    assert resumed.optimizer.state[resumed.model.weight]["step"].item() == 894
    initial = training.read_checkpoint(training.checkpoint_ref(root / "step0596_branch"), f.rt)
    parent = training.read_checkpoint(f.parent["parent_checkpoint"], f.rt)
    assert v8._tree_digest(initial["rng"]) == v8._tree_digest(parent["rng"])
    assert v8._tree_digest(initial["parameters"]) == v8._tree_digest(parent["parameters"])


def test_hold_cannot_substitute_prior_or_new_distribution(toy_parent):
    f = toy_parent
    driver = tiny_driver(training.branch_root(f.root, 137, "Hold") / "training",
                         f.old.pool, f.old.schedule)
    with pytest.raises(ValueError, match="current parent pi"):
        training.execute_training(f.root, 137, "Hold", "protocol", driver, f.old.prior,
                                  rt=f.rt, monitor=f.monitor, distribution_source={"field": "prior"})
    assert not driver.root.exists()


def test_payload_rejects_foreign_parent_or_tensor_corruption(tmp_path):
    rt = SimpleNamespace(torch=torch, v8=v8)
    parent = dict(id="same-parent", parent_state_digest="parent-digest")
    worker.save_payload(tmp_path, {"gJ": {"p": torch.tensor([1.0, 2.0])}}, parent, "replay_C05", rt)
    with pytest.raises(ValueError, match="different parent"):
        worker.read_payload(tmp_path, {**parent, "id": "other-parent"}, "replay_C05", rt)
    assert torch.equal(worker.read_payload(tmp_path, parent, "replay_C05", rt)["gJ"]["p"],
                       torch.tensor([1.0, 2.0]))
    raw = bytearray((tmp_path / "payload/state.pt").read_bytes())
    raw[-20] ^= 1
    (tmp_path / "payload/state.pt").write_bytes(raw)
    with pytest.raises(ValueError, match="tensor bytes"):
        worker.read_payload(tmp_path, parent, "replay_C05", rt)


def test_old_outer_cannot_change_real_training_rng(toy_parent):
    f = toy_parent
    state = f.old._payload()
    post = copy.deepcopy(state)
    post["rng"]["torch"][0] ^= 1
    with pytest.raises(ValueError, match="training component: rng"):
        training.validate_old_outer(state, post, {"pre_state": state}, {}, rt=f.rt)


def test_complete_replay_payload_resume_does_no_response_replay(tmp_path, monkeypatch):
    import finqa_v54_temperature as temperature

    rt = SimpleNamespace(torch=torch, v8=v8)
    parent = dict(id="parent", parent_state_digest="full-parent", point_id="same-point")
    gradients = {"w": torch.tensor([1.0, 2.0])}
    report = dict(complete_replay=True, denominator=700, point_id="same-point",
                  feedback_condition_id="condition", temperature=0.5,
                  gJ_digest=v8.parameter_digest(gradients),
                  response_checkpoint_binding={"response_count": 2})
    worker.save_payload(tmp_path, dict(gJ=gradients, report=report,
                        condition={"id": "condition", "temperature": 0.5}),
                        parent, "replay_C05", rt)

    def forbidden_replay(*args, **kwargs):
        raise AssertionError("complete actual gJ must be reused")

    monkeypatch.setattr(temperature, "feedback_gradient", forbidden_replay)
    result = worker.execute_replay(tmp_path, tmp_path, parent, None, None, None, rt, None)
    assert result["completed_payload_reused"] and result["replayed_responses"] == 0


@pytest.mark.parametrize("bad", ({"t": {"a": 0.0, "b": 1.0}},
                                  {"t": {"a": 0.5}},
                                  {"t": {"a": 0.2, "b": 0.2}}))
def test_support_and_normalization_fail_closed(bad):
    with pytest.raises(ValueError):
        training.validate_distribution(bad, {"t": {"a": 0.4, "b": 0.6}})
