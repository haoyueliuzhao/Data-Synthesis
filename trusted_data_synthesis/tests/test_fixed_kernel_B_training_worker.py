"""Synthetic CPU shared-prefix, durable-resume and strict admission controls."""

import copy
import importlib
import random
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest
import torch

sys.path.insert(0, str(Path(__file__).parents[1] / "scripts"))
w = importlib.import_module("fixed_kernel_B_training_worker_20260922")
p = w.p


def tiny_runtime(tmp_path):
    raw = tmp_path / "raw"
    tasks = [f"task_{i}" for i in range(200)]
    packages = [
        dict(package_id=f"package_{i}", task_id=task, state_id="state")
        for i, task in enumerate(tasks)
    ]
    cache = SimpleNamespace(
        cache_id="cache_B",
        packages=packages,
        actual_budget=dict(
            packages_per_epoch=200,
            rows_per_epoch=200,
            sequence_tokens_per_epoch=1400,
            target_tokens_per_epoch=400,
        ),
    )
    materials = dict(
        binding=dict(prior={task: {"state": "1"} for task in tasks}, control_tasks=[]),
        binding_id="synthetic_B_binding",
        trajectory_cache=dict(cache_root="cache", manifest_id="cache_B"),
        assets=dict(base_binding={}),
        initial_adapter_digests={"11": "paired_tiny"},
        training_configuration={},
        training_groups=dict.fromkeys(tasks, "control"),
        schedules={
            "11": dict(
                batches=[
                    dict(step=i, epoch=i // 40, task_ids=tasks[(i % 40) * 5 : (i % 40 + 1) * 5])
                    for i in range(400)
                ]
            )
        },
    )
    jobs = [
        dict(
            key=f"B_{condition}_11",
            condition=condition,
            seed=11,
            pool="B",
            start=0 if condition == "prefix" else 200,
            stop=200 if condition == "prefix" else 400,
            prefix_key="B_prefix_11",
        )
        for condition in ("prefix", "static", "delayed_c")
    ]
    plan = dict(id="test_B_plan", materials=materials, training_jobs=jobs)
    p.write_once(tmp_path / "cache/manifest.json", {"id": "cache_B"})
    events, reservations, calls = [], [], []
    fail_once = {"step": None}

    def write(path, value, immutable=True):
        if fail_once["step"] == str(path):
            fail_once["step"] = None
            raise RuntimeError("injected_after_atomic_checkpoint")
        if path.exists():
            assert p.read_json(path) == value
        else:
            p.write_once(path, value)

    def model_loader(binding, seed, trainable):
        calls.append(seed)
        torch.manual_seed(seed)
        random.seed(seed)
        return torch.nn.Linear(1, 1, bias=False), {}

    def by_task_at_pi(selected_cache, pi):
        # A simulated setup helper consuming randomness must not pollute resume RNG.
        torch.rand(3)
        random.random()
        return {row["task_id"]: [(i, row)] for i, row in enumerate(selected_cache.packages)}

    def update(model, optimizer, chosen, batch, **kwargs):
        assert kwargs["pool"] == "B" and str(kwargs["device"]) == "cpu"
        optimizer.zero_grad()
        loss = (model.weight * (torch.rand(1) + random.random())).square().sum()
        loss.backward()
        optimizer.step()
        return p.record(
            "optimizer_update",
            pool="B",
            arm=kwargs["arm"],
            optimizer_step_calls=1,
            cache_id="cache_B",
            packages=chosen,
            tasks=batch["tasks"],
            target_tokens=2 * len(chosen),
            sequence_tokens=7 * len(chosen),
            rows_completed=len(chosen),
            packages_completed=len(chosen),
            weighted_loss=float(loss.detach()),
        )

    def save_training(path, names, optimizer, step, report, plan_id, job_key):
        parameter = next(iter(names.values())).detach().clone()
        snapshot = p.record(
            "synthetic_snapshot",
            step=step,
            theta=parameter.tolist(),
            optimizer_steps=[int(state["step"]) for state in optimizer.state.values()],
        )
        checkpoint = dict(
            plan_id=plan_id,
            job_key=job_key,
            completed_updates=step,
            snapshot=snapshot,
            state=dict(theta=parameter, optimizer=copy.deepcopy(optimizer.state_dict())),
            rng=dict(
                cpu=torch.get_rng_state(),
                python=random.getstate(),
                schedule_cursor=step,
                cuda=[],
                numpy=None,
            ),
            update_report=report,
        )
        path.parent.mkdir(parents=True, exist_ok=True)
        assert not path.exists()
        torch.save(checkpoint, path)

    def load_training(path, plan_id, allowed_job_keys, step=None):
        value = torch.load(path, map_location="cpu", weights_only=False)
        assert value["plan_id"] == plan_id and value["job_key"] in allowed_job_keys
        assert step is None or value["completed_updates"] == step
        assert value["rng"]["schedule_cursor"] == value["completed_updates"]
        return value

    def restore_optimizer(names, optimizer, state, snapshot, step):
        with torch.no_grad():
            next(iter(names.values())).copy_(state["theta"])
        optimizer.load_state_dict(state["optimizer"])
        assert all(int(value["step"]) == step for value in optimizer.state.values())

    def restore_rng(rng):
        torch.set_rng_state(rng["cpu"])
        random.setstate(rng["python"])

    old = SimpleNamespace(
        trajectory_materials=SimpleNamespace(load_pool=lambda *_: cache),
        classes=SimpleNamespace(admit=lambda *_: None),
        components=SimpleNamespace(adapter_digest=lambda _: "paired_tiny"),
        trajectory_training=SimpleNamespace(
            load_registered_student=model_loader,
            optimizer_factory=lambda names, _: torch.optim.AdamW(names, lr=1e-3),
        ),
        inner=SimpleNamespace(execute_update=update),
    )
    api = SimpleNamespace(
        RAW=raw,
        old=old,
        d=SimpleNamespace(by_task_at_pi=by_task_at_pi),
        s=SimpleNamespace(restore_optimizer=restore_optimizer, restore_rng=restore_rng),
        read_protocol=lambda _: plan,
        write=write,
        emit=events.append,
        capacity_boundary=lambda *_, **__: None,
        reserve=lambda *args: reservations.append(args),
        save_training=save_training,
        load_training=load_training,
    )
    return api, plan, reservations, calls, fail_once


def test_shared_real_Adam_RNG_forks_resume_without_repeating_committed_update(
    tmp_path, monkeypatch
):
    c, plan, reservations, calls, fail_once = tiny_runtime(tmp_path)
    monkeypatch.setattr(w, "_common", lambda: c)
    prefix = w.run(tmp_path, "B_prefix_11", 1)
    assert prefix["physical_optimizer_updates"] == 200
    fail_once["step"] = str(c.RAW / "jobs/B_static_11/updates/0201.json")
    with pytest.raises(RuntimeError, match="injected_after_atomic_checkpoint"):
        w.run(tmp_path, "B_static_11", 1)
    static = w.run(tmp_path, "B_static_11", 2)
    assert static["effective_optimizer_updates"] == 400
    assert static["physical_optimizer_updates"] == static["shared_prefix_updates_reused"] == 200
    assert static["updates_in_final_attempt"] == 199
    assert len([r for r in reservations if r[1] == "B_static_11" and r[3] == 201]) == 1
    assert (c.RAW / "jobs/B_static_11/updates/0201.json").exists()

    updated = p.record(
        "anchored_sources_distribution_step", pi_next=plan["materials"]["binding"]["prior"]
    )
    outer = c.RAW / "outer/B_delayed_c_11"
    p.write_once(outer / "distribution_update.json", updated)
    p.write_once(
        outer / "report.json",
        dict(
            plan_id=plan["id"],
            job_key="B_delayed_c_11",
            numeric_guard_passed=True,
            prefix_checkpoint_sha256=prefix["checkpoint_sha256"],
            prefix_snapshot_id=prefix["snapshot_id"],
            distribution_update_id=updated["id"],
        ),
    )
    delayed = w.run(tmp_path, "B_delayed_c_11", 1)
    a = c.load_training(Path(static["checkpoint_path"]), plan["id"], ["B_static_11"])
    b = c.load_training(Path(delayed["checkpoint_path"]), plan["id"], ["B_delayed_c_11"])
    assert torch.equal(a["state"]["theta"], b["state"]["theta"])
    assert a["snapshot"] == b["snapshot"]
    assert torch.equal(a["rng"]["cpu"], b["rng"]["cpu"])
    assert a["rng"]["python"] == b["rng"]["python"]
    for field in ("exp_avg", "exp_avg_sq", "step"):
        assert torch.equal(
            a["state"]["optimizer"]["state"][0][field], b["state"]["optimizer"]["state"][0][field]
        )
    assert len(reservations) == 600  # One 200-step prefix plus two 200-step tails.
    calls_before = len(calls)
    assert w.run(tmp_path, "B_static_11", 3) == static
    assert len(calls) == calls_before and len(reservations) == 600


def test_rejects_incomplete_prefix_and_noncontiguous_commits(tmp_path):
    c, plan, _, _, _ = tiny_runtime(tmp_path)
    job = w._job(plan, "B_static_11")
    with pytest.raises(FileNotFoundError):
        w._prefix(c, plan, job)
    directory = c.RAW / "jobs/B_prefix_11"
    (directory / "updates").mkdir(parents=True)
    (directory / "updates/0002.pt").touch()
    with pytest.raises(ValueError, match="contiguous_committed_updates"):
        w._recover_updates(c, directory, plan["id"], "B_prefix_11", 0, 200)


def test_guard_and_foreign_pool_are_blocking(tmp_path):
    c, plan, _, _, _ = tiny_runtime(tmp_path)
    plan["training_jobs"][0]["pool"] = "A"
    with pytest.raises(ValueError, match="B_seed"):
        w._job(plan, "B_prefix_11")
    job = w._job(plan, "B_delayed_c_11")
    updated = p.record(
        "anchored_sources_distribution_step", pi_next=plan["materials"]["binding"]["prior"]
    )
    outer = c.RAW / "outer/B_delayed_c_11"
    p.write_once(outer / "distribution_update.json", updated)
    p.write_once(
        outer / "report.json",
        dict(
            plan_id=plan["id"],
            job_key=job["key"],
            prefix_checkpoint_sha256="prefix",
            prefix_snapshot_id="snapshot",
            numeric_guard_passed=False,
            distribution_update_id=updated["id"],
        ),
    )
    with pytest.raises(ValueError, match="only_bound_completed_outer_with_passed_guard"):
        w._distribution(
            c, plan, job, dict(prefix_checkpoint_sha256="prefix", prefix_snapshot_id="snapshot")
        )
