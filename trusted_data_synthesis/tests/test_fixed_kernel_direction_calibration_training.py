"""Tiny CPU proof of exact prefix restore, fixed schedule and atomic resume."""

import importlib
import random
import sys
from contextlib import contextmanager
from pathlib import Path
from types import SimpleNamespace

import numpy as np
import pytest
import torch

sys.path.insert(0, str(Path(__file__).parents[1] / "scripts"))
w = importlib.import_module("fixed_kernel_direction_calibration_training_20260926")
m = w.admission
p, real = w.p, m.b


def runtime(tmp_path):
    old_raw, new_raw = tmp_path / "historical_B", tmp_path / "new_calibration"
    calls, reservations, update_steps, events = [], [], [], []
    fail = {"after_checkpoint": None, "before_update": None, "capacity_step": None}
    tasks = [f"task{i}" for i in range(200)]
    packages = [
        dict(package_id=task, task_id=task, state_id="state", coefficient_float=0.2)
        for task in tasks
    ]
    budget = dict(
        packages_per_epoch=200,
        rows_per_epoch=200,
        sequence_tokens_per_epoch=1400,
        target_tokens_per_epoch=400,
    )
    cache = SimpleNamespace(packages=packages, actual_budget=budget, cache_id="cache")

    def make_model(seed):
        torch.manual_seed(seed)
        random.seed(seed)
        np.random.seed(seed)
        return torch.nn.Linear(1, 1, bias=False)

    def make_optimizer(values, configuration):
        return torch.optim.AdamW(values, lr=1e-3)

    def tiny_update(model, optimizer):
        optimizer.zero_grad()
        multiplier = torch.rand(1) + random.random() + np.random.random()
        loss = (model.weight * multiplier).square().sum()
        loss.backward()
        torch.nn.utils.clip_grad_norm_(model.parameters(), 1)
        optimizer.step()
        return float(loss.detach())

    def save(path, names, optimizer, step, report, plan_id, key):
        bound = real.old.adam.bind_adamw(names, optimizer, clip_max_norm=1)
        state = {}
        for row in bound.parameters:
            for prefix, value in (
                ("theta", row.theta),
                ("first_moment", row.first),
                ("second_moment", row.second),
            ):
                state[prefix + "/" + row.name] = value.detach().cpu().clone()
        rng = real.s.capture_rng(step, cuda=False)
        rng["cuda"] = [rng["cpu"].clone()]  # Synthetic stored stream; never initialize CUDA.
        real.s.atomic_torch(
            path,
            dict(
                kind="B_shared_training_state",
                plan_id=plan_id,
                job_key=key,
                completed_updates=step,
                snapshot=bound.snapshot,
                state=state,
                rng=rng,
                update_report=report,
            ),
        )

    model = make_model(11)
    optimizer = make_optimizer(model.parameters(), {})
    for _ in range(200):
        tiny_update(model, optimizer)
    prefix_path = old_raw / "jobs/B_prefix_11/updates/0200.pt"
    save(
        prefix_path,
        dict(model.named_parameters()),
        optimizer,
        200,
        p.record("optimizer_update", historical=True),
        "original-plan",
        "B_prefix_11",
    )
    saved = real.load_training(prefix_path, "original-plan", ["B_prefix_11"], step=200)
    reference = dict(
        path=str(prefix_path),
        sha256=p.sha(prefix_path),
        job_key="B_prefix_11",
        step=200,
        snapshot_id=saved["snapshot"]["id"],
        RNG_binding=m._rng_binding(saved["rng"], 200),
    )
    pi = {task: {"state": 1.0} for task in tasks}
    binding = dict(id="material", prior=pi, control_tasks=tasks)
    reflection = p.record(
        "direction_calibration_reflection",
        distributions={"negative": pi},
        distribution_sha256={"negative": p.sha(p.encode(pi))},
        binding_id=binding["id"],
        probability_clipping_or_repair=False,
    )
    materials = dict(
        binding=binding,
        actual_budget=budget,
        trajectory_cache=dict(cache_root="cache", manifest_id="cache"),
        assets=dict(base_binding={}),
        initial_adapter_digests={"11": "same_initial"},
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
    admitted = p.record(
        "direction_calibration_material_admission",
        passed=True,
        seeds=[11, 29, 47],
        original_protocol_id="original-plan",
        materials=materials,
        reusable_refs=[reference],
        distributions={"11": reflection},
    )
    plan = dict(id="new-plan", seeds=[11, 29, 47], materials_admission=admitted)
    p.write_once(tmp_path / "cache/manifest.json", dict(id="cache"))

    def write(path, value, immutable=True):
        assert path.is_relative_to(new_raw)
        if fail["after_checkpoint"] == path.name:
            fail["after_checkpoint"] = None
            raise RuntimeError("injected after durable checkpoint")
        if path.exists():
            assert p.read_json(path) == value
        else:
            p.write_once(path, value)

    def loader(base, seed, trainable):
        assert trainable is True
        calls.append(seed)
        return make_model(seed), {}

    def by_task(selected, distribution):
        assert distribution == pi
        # Setup may consume RNG; restoring the saved prefix follows all setup.
        torch.rand(5)
        random.random()
        np.random.random()
        return {row["task_id"]: [(i, row)] for i, row in enumerate(selected.packages)}

    def update(model, optimizer, chosen, details, **kwargs):
        assert kwargs["pool"] == "B" and kwargs["arm"] == "negative"
        assert str(kwargs["device"]) == "cpu" and model.training
        step = details["step"] + 1
        if fail["before_update"] == step:
            fail["before_update"] = None
            raise RuntimeError("injected after reservation before commit")
        loss = tiny_update(model, optimizer)
        update_steps.append(step)
        return p.record(
            "optimizer_update",
            pool="B",
            arm="negative",
            cache_id="cache",
            optimizer_step_calls=1,
            tasks=details["tasks"],
            packages=chosen,
            target_tokens=2 * len(chosen),
            sequence_tokens=7 * len(chosen),
            rows_completed=len(chosen),
            packages_completed=len(chosen),
            weighted_loss=loss,
        )

    @contextmanager
    def locked(path, blocking):
        assert path.is_relative_to(new_raw) and blocking is False
        yield None

    def reserve(*args):
        reservations.append(args)

    def capacity(*args, **kwargs):
        if fail["capacity_step"] is not None and len(update_steps) == fail["capacity_step"]:
            fail["capacity_step"] = None
            raise RuntimeError("capacity at committed boundary")

    old = SimpleNamespace(
        classes=SimpleNamespace(admit=lambda *a: None),
        trajectory_materials=SimpleNamespace(load_pool=lambda *a: cache),
        components=SimpleNamespace(adapter_digest=lambda *a: "same_initial"),
        trajectory_training=SimpleNamespace(
            load_registered_student=loader, optimizer_factory=make_optimizer
        ),
        inner=SimpleNamespace(execute_update=update),
    )
    c = SimpleNamespace(
        RAW=new_raw,
        b=SimpleNamespace(
            old=old,
            d=SimpleNamespace(by_task_at_pi=by_task),
            load_training=real.load_training,
            save_training=save,
        ),
        s=SimpleNamespace(
            restore_optimizer=real.s.restore_optimizer,
            restore_rng=lambda rng: real.s.restore_rng(rng, cuda=False),
        ),
        read_protocol=lambda root: plan,
        write=write,
        locked=locked,
        reserve=reserve,
        capacity_boundary=capacity,
        emit=events.append,
    )
    return c, plan, reference, calls, reservations, update_steps, fail


def final_state(c):
    return real.load_training(
        c.RAW / "jobs/B_negative_11/updates/0240.pt", "new-plan", ["B_negative_11"], step=240
    )


def test_fixed_40_step_negative_epoch_and_completed_idempotence(tmp_path):
    c, plan, reference, calls, reservations, steps, fail = runtime(tmp_path)
    report = w.run(c, tmp_path, 11, 1)
    assert steps == list(range(201, 241))
    assert [row[-1] for row in reservations] == steps
    assert all(row[:3] == ("optimizer", "B_negative_11", 1) for row in reservations)
    assert report["physical_optimizer_updates"] == 40
    assert report["effective_optimizer_updates"] == 240
    assert report["shared_prefix_updates_reused"] == 200
    assert report["physical_job_totals"] == dict(
        target_tokens=400, sequence_tokens=1400, rows_completed=200, packages_completed=200
    )
    assert (
        report["new_positive_or_static_updates"]
        == report["generation_sessions"]
        == report["scoring_sessions"]
        == 0
    )
    assert p.sha(Path(reference["path"])) == reference["sha256"]
    assert w.run(c, tmp_path, 11, 2) == report
    assert calls == [11] and len(reservations) == 40


def test_checkpoint_committed_before_JSON_interruption_resumes_exactly(tmp_path):
    c, plan, reference, calls, reservations, steps, fail = runtime(tmp_path / "interrupted")
    fail["after_checkpoint"] = "0201.json"
    with pytest.raises(RuntimeError, match="after durable checkpoint"):
        w.run(c, tmp_path / "interrupted", 11, 1)
    checkpoint = c.RAW / "jobs/B_negative_11/updates/0201.pt"
    assert checkpoint.exists() and not checkpoint.with_suffix(".json").exists()
    report = w.run(c, tmp_path / "interrupted", 11, 2)
    assert report["updates_in_final_attempt"] == 39
    assert len(reservations) == 40 and steps == list(range(201, 241))
    clean, *_ = runtime(tmp_path / "clean")
    w.run(clean, tmp_path / "clean", 11, 1)
    a, b = final_state(c), final_state(clean)
    assert a["snapshot"] == b["snapshot"]
    assert all(torch.equal(a["state"][key], b["state"][key]) for key in a["state"])
    assert m._rng_binding(a["rng"], 240) == m._rng_binding(b["rng"], 240)
    assert p.sha(Path(reference["path"])) == reference["sha256"]


def test_partial_update_is_charged_and_repeat_requires_new_attempt(tmp_path):
    c, plan, reference, calls, reservations, steps, fail = runtime(tmp_path)
    fail["before_update"] = 202
    with pytest.raises(RuntimeError, match="after reservation"):
        w.run(c, tmp_path, 11, 1)
    report = w.run(c, tmp_path, 11, 2)
    assert len(reservations) == 41
    assert [row[2] for row in reservations if row[-1] == 202] == [1, 2]
    assert steps == list(range(201, 241))
    assert report["physical_optimizer_updates"] == 40
    assert report["uncommitted_attempt_budget_accounted_separately_by_reservations"] is True


def test_capacity_exit_is_saved_boundary_and_restarts_without_duplicate_update(tmp_path):
    c, plan, reference, calls, reservations, steps, fail = runtime(tmp_path)
    fail["capacity_step"] = 2
    with pytest.raises(RuntimeError, match="capacity at committed boundary"):
        w.run(c, tmp_path, 11, 1)
    w.run(c, tmp_path, 11, 2)
    assert steps == list(range(201, 241)) and len(reservations) == 40


@pytest.mark.parametrize("seed", [12, "11", True])
def test_unregistered_seed_never_initializes_model_or_reserves(tmp_path, seed):
    c, plan, reference, calls, reservations, steps, fail = runtime(tmp_path)
    with pytest.raises(ValueError, match="fixed_seed"):
        w.run(c, tmp_path, seed, 1)
    assert calls == reservations == steps == []


def test_historical_B_output_directory_is_forbidden(tmp_path):
    c, plan, reference, calls, reservations, steps, fail = runtime(tmp_path)
    c.RAW = Path(reference["path"]).parents[3]
    with pytest.raises(ValueError, match="never_write_historical_B"):
        w.run(c, tmp_path, 11, 1)
    assert calls == reservations == []


def test_noncontiguous_checkpoint_and_changed_prefix_fail_closed(tmp_path):
    c, plan, reference, calls, reservations, steps, fail = runtime(tmp_path)
    folder = c.RAW / "jobs/B_negative_11/updates"
    folder.mkdir(parents=True)
    real.s.atomic_torch(folder / "0202.pt", {})
    with pytest.raises(ValueError, match="contiguous_committed_updates"):
        w.run(c, tmp_path, 11, 1)
    assert calls == reservations == []
    changed = {**reference, "sha256": "0" * 64}
    with pytest.raises(ValueError, match="original_prefix_bytes"):
        w._prefix(c, plan["materials_admission"], changed)


def test_refused_budget_propagates_before_any_update(tmp_path):
    c, plan, reference, calls, reservations, steps, fail = runtime(tmp_path)

    def exhausted(*args):
        raise ValueError("finite optimizer budget exhausted")

    c.reserve = exhausted
    with pytest.raises(ValueError, match="budget exhausted"):
        w.run(c, tmp_path, 11, 1)
    assert steps == []
    assert not list((c.RAW / "jobs/B_negative_11/updates").glob("*.pt"))
