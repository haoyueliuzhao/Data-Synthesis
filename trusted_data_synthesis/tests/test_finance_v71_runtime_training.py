"""Fixed distribution, exact dose and true durable recovery CPU controls."""
from __future__ import annotations

import copy
import hashlib
import json
from pathlib import Path
from types import SimpleNamespace

import pytest

import finqa_v71_binding as binding
import finqa_v71_training as training
import finqa_v71_runtime as runtime


class Monitor:
    def __init__(self, stop=None):
        self.stop = stop

    def check_stop(self, _label, **fields):
        if fields.get("step") == self.stop:
            raise RuntimeError("requested durable pause")

    def clear_unused(self, _label):
        pass


class Driver:
    def __init__(self, root, state):
        self.root = root / "training"
        self.state = copy.deepcopy(state)
        self.outer_steps = (298, 596, 894, 1192)
        self.steps, self.commits = [], []

    @property
    def arm(self):
        return self.state["arm"]

    @property
    def pi(self):
        return self.state["pi"]

    @property
    def outer_done(self):
        return self.state["outer_done"]

    @property
    def step_index(self):
        return self.state["step"]

    def _payload(self):
        return copy.deepcopy(self.state)

    def restore(self, directory):
        self.state = json.loads((Path(directory) / "state.pt").read_bytes())

    def commit(self, phase, evidence):
        assert phase == "step", "fixed branch must never create an outer checkpoint"
        directory = self.root / f"step{self.step_index:04d}_{phase}"
        directory.mkdir(parents=True, exist_ok=False)
        raw = json.dumps(self.state, sort_keys=True).encode()
        (directory / "state.pt").write_bytes(raw)
        (directory / "record.json").write_text(json.dumps(dict(
            step=self.step_index, phase=phase, arm=self.arm, seed=137,
            pool_id=self.state["pool_id"],
            schedule_sha256=self.state["schedule"]["schedule_sha256"],
            checkpoint_contains_actual_model_Adam_RNG_pi=True,
            state_sha256=hashlib.sha256(raw).hexdigest(),
            actual_state_digest=binding.digest(self.state), evidence=evidence)))
        self.commits.append((self.step_index, phase))

    def step(self):
        assert self.outer_steps == () and self.arm == "C-only"
        assert self.step_index < self.final_step
        expected = self.state["schedule"]["batches"][self.step_index]
        self.state["step"] += 1
        self.state["parameters"] += 1
        self.state["optimizer"] += 1
        self.state["rng"] += 1
        self.steps.append(self.step_index)
        report = dict(id="update-" + str(self.step_index),
            optimizer_step_calls=1, clip_calls=1, actual_parameter_update=True,
            CPU_control_only=False, execution_design="original_unfused_response_rows_v18",
            supervision_policy="v14_state_independent_original_span_union.v1",
            additional_batch_division=False, additional_loss_scaling=False,
            task_batch=dict(task_ids=expected["task_ids"], step=self.step_index,
                            schedule_id=self.state["schedule"]["schedule_sha256"]))
        self.commit("step", report)
        return report


@pytest.fixture
def environment(tmp_path, monkeypatch):
    for module in (binding, training, runtime):
        monkeypatch.setattr(module, "ROOT", tmp_path)
    # State-machine fixtures use integer optimizer/RNG counters. The actual
    # tensor endpoint validator is exercised separately below.
    monkeypatch.setattr(training, "validate_point_state", lambda state, _step, _rt: state)
    schedule = dict(schedule_sha256="original-ten-epoch", batches=[
        {"task_ids": [f"task{n}" for n in range(4 if (i + 1) % 149 == 0 else 5)]}
        for i in range(1490)])
    state = {key: 1 for key in training.records.COMPONENTS}
    state.update(seed=137, arm="C-only", step=894, outer_done=[298],
                 pi={"task": {"a": 0.7, "b": 0.3}},
                 prior={"task": {"a": 0.5, "b": 0.5}}, optimizer=894,
                 parameters=12, rng=23, schedule=schedule, pool_id="actual-pool",
                 execution_plan={"outer_steps": [298, 596, 894, 1192], "final_step": 1490},
                 adapter_binding="actual-adapter", frozen_base_digest="actual-base")
    point = dict(schema="v71_fixed_distribution_window.v1", id="point894", step=894,
        final_step=1192, seed=137, arm="Fixed894", condition="fixed_pi894",
        checkpoint_arm="C-only", protocol_id="protocol-v71", parent_state_digest=binding.digest(state),
        initial_checkpoint={"path": "exact-original894"}, outer_done=[298],
        parent_pi=copy.deepcopy(state["pi"]), fixed_pi=copy.deepcopy(state["pi"]),
        fixed_pi_digest=binding.digest(state["pi"]), pool_id="actual-pool",
        new_outer_updates=0, automatic_outer_disabled=True,
        fixed_component_digests={key: binding.digest(state[key]) for key in training.FIXED_COMPONENTS},
        component_digests={"rng": binding.digest(state["rng"])},
        original_schedule_sha256="original-ten-epoch", window_task_batches=schedule["batches"][894:1192])
    rt = SimpleNamespace(v8=SimpleNamespace(_tree_digest=binding.digest))
    return SimpleNamespace(root=tmp_path, state=state, point=point, rt=rt)


def run(e, driver, monitor=None):
    return training.execute_training(e.root, e.point, e.state, driver,
        rt=e.rt, monitor=monitor or Monitor())


def test_exact_first_window_keeps_actual_pi_not_prior_and_original_history(environment):
    e = environment
    driver = Driver(e.root, e.state)
    result = run(e, driver)
    assert driver.steps == list(range(895, 1193))
    assert len(driver.commits) == 298 and all(phase == "step" for _, phase in driver.commits)
    assert driver.pi == e.state["pi"] != e.state["prior"] and driver.outer_done == [298]
    assert driver.arm == "C-only" and result["arm"] == "Fixed894"
    assert result["optimizer_updates"] == 298 and result["outer_updates"] == 0
    assert result["task_exposures"] == 1488 and len(result["update_receipts"]) == 298
    assert [len(row["task_ids"]) for row in e.point["window_task_batches"]].count(4) == 2
    assert not list(driver.root.glob("*_outer"))


def test_durable_resume_only_continues_after_actual_committed_prefix(environment):
    e = environment
    first = Driver(e.root, e.state)
    with pytest.raises(RuntimeError, match="durable pause"):
        run(e, first, Monitor(stop=1001))
    second = Driver(e.root, e.state)
    result = run(e, second)
    assert first.steps == list(range(895, 1001))
    assert second.steps == list(range(1001, 1193))
    assert result["updates_in_final_worker"] == 192
    assert second.state["rng"] == e.state["rng"] + 298


def test_completed_window_is_cold_restored_without_training_again(environment):
    e = environment
    result = run(e, Driver(e.root, e.state))
    with pytest.raises(ValueError, match="cannot execute again"):
        run(e, Driver(e.root, e.state))
    restored = Driver(e.root, e.state)
    training.restore_completed_window(e.point, result, restored, e.rt)
    assert restored.step_index == 1192 and restored.pi == e.state["pi"]
    assert not restored.steps and not restored.commits and restored.outer_done == [298]


def test_second_window_gives596_actual_updates_with_zero_new_outer(environment):
    e = environment
    first = Driver(e.root, e.state)
    run(e, first)
    e.state = copy.deepcopy(first.state)
    e.point = dict(e.point, id="point1192", step=1192, final_step=1490,
        parent_state_digest=binding.digest(e.state),
        component_digests={"rng": binding.digest(e.state["rng"])},
        window_task_batches=e.state["schedule"]["batches"][1192:1490])
    second = Driver(e.root, e.state)
    result = run(e, second)
    assert first.steps + second.steps == list(range(895, 1491))
    assert second.outer_done == [298] and second.pi == e.point["fixed_pi"]
    assert result["final_step"] == 1490 and not list(second.root.glob("*_outer"))
    assert sum(len(batch["task_ids"]) for batch in e.state["schedule"]["batches"][894:1490]) == 2976


@pytest.mark.parametrize("component", ["rng", "optimizer", "parameters"])
def test_exact_parent_is_required_before_first_real_update(environment, component):
    e = environment
    driver = Driver(e.root, e.state)
    driver.state[component] += 1
    with pytest.raises(ValueError, match="exact real parent"):
        run(e, driver)
    assert not driver.steps and not driver.commits


@pytest.mark.parametrize("mutation", ["pi", "outer_done", "schedule"])
def test_saved_fixed_components_cannot_change_even_on_resume(environment, mutation):
    e = environment
    with pytest.raises(RuntimeError):
        run(e, Driver(e.root, e.state), Monitor(stop=900))
    path = e.root / "training/step0899_step/state.pt"
    state = json.loads(path.read_bytes())
    state[mutation] = ({"task": {"a": .5, "b": .5}} if mutation == "pi" else
                       [298, 894] if mutation == "outer_done" else {"foreign": True})
    path.write_text(json.dumps(state))
    with pytest.raises(ValueError, match="pi0|history|component"):
        run(e, Driver(e.root, e.state))


def test_task_receipt_mismatch_blocks_completion(environment):
    e = environment
    with pytest.raises(RuntimeError):
        run(e, Driver(e.root, e.state), Monitor(stop=900))
    path = e.root / "training/step0895_step/record.json"
    record = json.loads(path.read_bytes())
    record["evidence"]["task_batch"]["task_ids"] = ["wrong-task"]
    path.write_text(json.dumps(record))
    with pytest.raises(ValueError, match="task batch order"):
        run(e, Driver(e.root, e.state))
    assert not (e.root / "points/step0894/train/completed/record.json").exists()


@pytest.mark.parametrize("name", ["step0894_outer", "step1192_outer", "step1491_step"])
def test_outer_and_out_of_budget_checkpoint_refuse_resume(environment, name):
    e = environment
    (e.root / "training" / name).mkdir(parents=True)
    with pytest.raises(ValueError, match="forbids|dose"):
        training.latest_window_checkpoint(e.root / "training", 894)


def test_partial_checkpoint_is_not_a_resume_boundary(environment):
    e = environment
    (e.root / "training/step0895_step").mkdir(parents=True)
    with pytest.raises(ValueError, match="partial checkpoint"):
        training.latest_window_checkpoint(e.root / "training", 894)


@pytest.mark.parametrize("step,stage", [(1490, "train"), (894, "distribution"),
                                       (894, "replay"), (894, "shard00"), (894, "virtual_point")])
def test_runtime_has_no_scientific_outer_or_terminal_training_dispatch(environment, step, stage):
    with pytest.raises(ValueError, match="only fixed-distribution"):
        runtime.stage_root(environment.root, step, stage)


def test_resume_audit_counts_optimizer_only_and_requires_contiguous_receipts(environment):
    e = environment
    e.point = binding.publish(e.root / "points/step0894/context/record.json", e.point)
    with pytest.raises(RuntimeError):
        run(e, Driver(e.root, e.state), Monitor(stop=900))
    job = runtime.job_spec(894)
    audit = training.audit_training_resume(e.root, job)
    assert audit["resume_allowed"] and audit["progress_units"] == 5
    assert audit["details"]["new_outer_commits"] == 0 and audit["unknown_calls"] == 0
    (e.root / "training/step0897_step/record.json").unlink()
    with pytest.raises(ValueError, match="partial checkpoint"):
        training.audit_training_resume(e.root, job)


def test_native_serializer_restore_preserves_rng_and_plan_with_runtime_outer_disabled(tmp_path):
    import torch
    from types import FunctionType, MethodType
    from trusted_synthesis.finance_research import v8_training_driver as v8
    assert Path(v8.__file__).resolve().is_relative_to(
        Path(binding.install_scientific_paths()["frozen_source_root"]))
    real = v8.TrainingDriver
    model = torch.nn.Linear(2, 1)
    optimizer = torch.optim.AdamW(model.parameters(), lr=1e-4, weight_decay=0)
    for parameter in model.parameters():
        optimizer.state[parameter] = dict(step=torch.tensor(894.),
            exp_avg=torch.zeros_like(parameter), exp_avg_sq=torch.ones_like(parameter))
    driver = object.__new__(real)
    driver.root, driver.model, driver.optimizer = tmp_path / "native", model, optimizer
    driver.pool = SimpleNamespace(cache_id="tiny-fixed-pool")
    driver.seed, driver.arm = 137, "C-only"
    driver.parameters = dict(model.named_parameters())
    driver.schedule = dict(schedule_sha256="same-ten-epoch", batches=[])
    driver.execution_plan = dict(outer_steps=[298, 596, 894, 1192], final_step=1490)
    driver.adapter_binding, driver.base_digest = None, "same-frozen-base"
    driver.pi = {"task": {"a": .7, "b": .3}}
    driver.prior = {"task": {"a": .5, "b": .5}}
    driver.step_index, driver.outer_done = 894, [298]
    driver.outer_steps, driver.final_step = (298, 596, 894, 1192), 1490
    fixed_rng = dict(cpu=torch.tensor([7, 11], dtype=torch.uint8), cuda=None, fixture_only=True)
    restored_rng = []

    def bind(function, **overrides):
        function_copy = FunctionType(function.__code__, dict(function.__globals__, **overrides),
                                    function.__name__, function.__defaults__, function.__closure__)
        function_copy.__kwdefaults__ = function.__kwdefaults__
        return MethodType(function_copy, driver)

    driver._payload = bind(real._payload, _rng=lambda: copy.deepcopy(fixed_rng))
    driver.restore = bind(real.restore, _restore_rng=lambda value: restored_rng.append(value))
    before = driver._payload()
    checkpoint = driver.commit("step", {"cpu_fixture_only": True})
    training.configure_fixed_window(driver, 894)
    assert v8._tree_digest(driver._payload()) == v8._tree_digest(before)
    with torch.no_grad():
        next(iter(driver.parameters.values())).add_(3)
    driver.restore(checkpoint)
    assert v8._tree_digest(driver._payload()) == v8._tree_digest(before)
    assert driver.execution_plan == dict(outer_steps=[298, 596, 894, 1192], final_step=1490)
    assert driver.final_step == 1192 and driver.outer_steps == () and driver.outer_done == [298]
    assert v8._tree_digest(restored_rng[0]) == v8._tree_digest(fixed_rng)


@pytest.mark.parametrize("cursor", [1192, 1191])
def test_actual_endpoint_adam_cursor_required(cursor):
    import torch
    pi = {f"task{i}": {"a": 1.0} for i in range(744)}
    state = dict(seed=137, step=1192, arm="C-only", outer_done=[298],
        model_training=True, rng={"cuda": [torch.tensor([1], dtype=torch.uint8)]},
        optimizer={"state": {0: dict(step=torch.tensor(float(cursor)),
            exp_avg=torch.tensor([0.]), exp_avg_sq=torch.tensor([1.]))}},
        pi=pi, prior=copy.deepcopy(pi),
        execution_plan=dict(outer_steps=[298, 596, 894, 1192], final_step=1490))
    if cursor == 1192:
        assert training.validate_point_state(state, 1192, None) is state
    else:
        with pytest.raises(ValueError, match="Adam cursor"):
            training.validate_point_state(state, 1192, None)


@pytest.mark.parametrize("returncode", [0, 1])
def test_second_window_requires_actual_accepted_exit_zero(environment, returncode):
    e = environment
    base = e.root / "points/step0894/train"
    actual_path = base / "attempts/attempt0001/actual_exit/record.json"
    binding.publish(actual_path, dict(protocol_id="protocol-v71", job_id="step894.train",
        actual_waitpid_observed=True, returncode=returncode))
    result_path = base / "result/record.json"
    result = binding.publish(result_path, dict(protocol_id="protocol-v71", job_id="step894.train",
        final_step=1192, optimizer_updates=298, outer_updates=0))
    binding.publish(base / "accepted/record.json", dict(protocol_id="protocol-v71",
        job_id="step894.train", actual_exit=binding.entry(actual_path),
        actual_exit_zero=True, resources_passed=True, result=binding.entry(result_path),
        result_id=result["id"]))
    if returncode == 0:
        assert training._accepted_previous_window(e.root, "protocol-v71")["id"]
    else:
        with pytest.raises(ValueError, match="accepted actual exit zero"):
            training._accepted_previous_window(e.root, "protocol-v71")
