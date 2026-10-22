"""Focused CPU state-machine controls; no actual model, GPU or API calls."""
from __future__ import annotations

import copy
import hashlib
import json
from pathlib import Path
from types import SimpleNamespace

import pytest

import finqa_v70_binding as binding
import finqa_v70_training as training
import finqa_v70_temperature as temperature
import finqa_v70_runtime as runtime


class Monitor:
    def __init__(self, stop=None):
        self.stop = stop

    def check_stop(self, _label, **fields):
        if fields.get("step") == self.stop:
            raise RuntimeError("requested mock durable pause")

    def clear_unused(self, _label):
        return None


class Driver:
    def __init__(self, root, state):
        self.root = root / "training"
        self.state = copy.deepcopy(state)
        self.outer_steps = (298, 596, 894, 1192)
        self.steps, self.commits = [], []

    @property
    def arm(self):
        return self.state["arm"]

    @arm.setter
    def arm(self, value):
        self.state["arm"] = value

    @property
    def pi(self):
        return self.state["pi"]

    @pi.setter
    def pi(self, value):
        self.state["pi"] = value

    @property
    def outer_done(self):
        return self.state["outer_done"]

    @outer_done.setter
    def outer_done(self, value):
        self.state["outer_done"] = value

    @property
    def step_index(self):
        return self.state["step"]

    def _payload(self):
        return copy.deepcopy(self.state)

    def restore(self, directory):
        state = json.loads((Path(directory) / "state.pt").read_bytes())
        assert state["arm"] == self.arm
        self.state = state

    def commit(self, phase, evidence):
        directory = self.root / f"step{self.step_index:04d}_{phase}"
        directory.mkdir(parents=True, exist_ok=False)
        raw = json.dumps(self.state, sort_keys=True).encode()
        (directory / "state.pt").write_bytes(raw)
        (directory / "record.json").write_text(json.dumps(dict(
            step=self.step_index, phase=phase, arm=self.arm, seed=137,
            state_sha256=hashlib.sha256(raw).hexdigest(),
            actual_state_digest=binding.digest(self.state), evidence=evidence)))
        self.commits.append((self.step_index, phase))

    def step(self):
        assert self.outer_steps == () and self.arm == "Full"
        assert self.step_index < self.final_step
        self.state["step"] += 1
        self.state["parameters"] += 1
        self.state["optimizer"] += 1
        self.state["rng"] += 1
        self.steps.append(self.step_index)
        report = dict(optimizer_step_calls=1, clip_calls=1)
        self.commit("step", report)
        return report


@pytest.fixture
def environment(tmp_path, monkeypatch):
    for module in (binding, training, runtime):
        monkeypatch.setattr(module, "ROOT", tmp_path)
    state = {key: 1 for key in training.records.COMPONENTS}
    state.update(seed=137, arm="C-only", step=894, outer_done=[298],
                 pi={"task": {"a": 0.5, "b": 0.5}},
                 prior={"task": {"a": 0.5, "b": 0.5}}, optimizer=894,
                 parameters=12, rng=23)
    point = dict(id="point894", step=894, probe_only=False, seed=137,
        protocol_id="new-protocol", parent_state_digest=binding.digest(state),
        outer_done=[298],
        component_digests={"rng": binding.digest(state["rng"])},
        original_schedule_sha256="original-ten-epoch")
    rt = SimpleNamespace(v8=SimpleNamespace(_tree_digest=binding.digest))
    return SimpleNamespace(root=tmp_path, state=state, point=point, rt=rt,
                           q={"task": {"a": 0.6, "b": 0.4}})


def run(e, driver, monitor=None, q=None):
    return training.execute_training(e.root, e.point, e.state, driver, q or e.q,
        rt=e.rt, monitor=monitor or Monitor(), distribution_source={"id": "formal-full-q"})


def test_exact_298_steps_one_explicit_transition_and_no_596_history_rewrite(environment):
    e = environment
    driver = Driver(e.root, e.state)
    result = run(e, driver)
    assert driver.steps == list(range(895, 1193))
    assert driver.commits[0] == (894, "outer")
    assert [row for row in driver.commits if row[1] == "outer"] == [(894, "outer")]
    assert driver.outer_done == [298, 894] and driver.pi == e.q and driver.arm == "Full"
    assert e.state["arm"] == "C-only" and e.state["outer_done"] == [298]
    assert result["optimizer_updates"] == 298 and result["outer_updates"] == 1
    assert result["task_exposures"] == 1488 and result["final_step"] == 1192
    outer = json.loads((driver.root / "step0894_outer/state.pt").read_bytes())
    assert all(outer[key] == e.state[key] for key in training.records.COMPONENTS
               if key not in ("pi", "outer_done"))


def test_durable_resume_does_not_repeat_outer_or_committed_steps(environment):
    e = environment
    first = Driver(e.root, e.state)
    with pytest.raises(RuntimeError, match="durable pause"):
        run(e, first, Monitor(stop=1001))
    assert first.steps == list(range(895, 1001))
    second = Driver(e.root, e.state)
    result = run(e, second)
    assert second.steps == list(range(1001, 1193))
    assert all(phase == "step" for _step, phase in second.commits)
    assert result["updates_in_final_worker"] == 192


def test_cold_resume_cannot_change_formal_q(environment):
    e = environment
    with pytest.raises(RuntimeError):
        run(e, Driver(e.root, e.state), Monitor(stop=900))
    with pytest.raises(ValueError, match="immutable V70 artifact differs"):
        run(e, Driver(e.root, e.state), q={"task": {"a": 0.7, "b": 0.3}})


def test_complete_window_cannot_train_again(environment):
    e = environment
    run(e, Driver(e.root, e.state))
    with pytest.raises(ValueError, match="completed window"):
        run(e, Driver(e.root, e.state))


def test_completed_window_cold_acceptance_restores_actual_endpoint(environment):
    e = environment
    result = run(e, Driver(e.root, e.state))
    restored = Driver(e.root, e.state)
    training.restore_completed_window(e.point, result, restored, e.q, e.rt)
    assert restored.step_index == 1192 and restored.outer_done == [298, 894]
    assert restored.arm == "Full" and not restored.steps and not restored.commits
    with pytest.raises(ValueError, match="metadata differs"):
        training.restore_completed_window(e.point, result, restored,
            {"task": {"a": 0.7, "b": 0.3}}, e.rt)


def test_second_window_keeps_first_checkpoint_and_exact_596_total(environment):
    e = environment
    first = Driver(e.root, e.state)
    run(e, first)
    e.state = copy.deepcopy(first.state)
    e.point = dict(e.point, id="point1192", step=1192,
        parent_state_digest=binding.digest(e.state),
        component_digests={"rng": binding.digest(e.state["rng"])})
    second = Driver(e.root, e.state)
    result = run(e, second, q={"task": {"a": 0.65, "b": 0.35}})
    assert first.steps + second.steps == list(range(895, 1491))
    assert second.outer_done == [298, 894, 1192]
    assert result["final_step"] == 1490 and (e.root / "training/step0894_outer").is_dir()
    assert not (e.root / "training/step1490_outer").exists()


def test_terminal_probe_cannot_apply_or_train(environment):
    e = environment
    e.point.update(step=1490, probe_only=True)
    with pytest.raises(ValueError, match="candidate-only"):
        run(e, Driver(e.root, e.state))
    with pytest.raises(ValueError, match="unregistered"):
        runtime.stage_root(e.root, 1490, "train")
    assert not (e.root / "training").exists()


def test_transition_requires_exact_real_parent_before_any_commit(environment):
    e = environment
    driver = Driver(e.root, e.state)
    driver.state["rng"] += 1
    with pytest.raises(ValueError, match="exact real parent"):
        run(e, driver)
    assert not driver.commits and not driver.steps


def test_parent_history_is_not_reconstructed_from_outer_schedule():
    assert training.expected_outer_history(894) == [298]
    assert training.expected_outer_history(1192) == [298, 894]
    assert training.expected_outer_history(1490) == [298, 894, 1192]


def test_temperature_namespace_is_private_and_T1_only():
    assert temperature.BACKEND_VERSION == "v70_T1_Full_exact_temperature_r3.v1"
    assert temperature._implementation.binding.ROOT == binding.ROOT
    assert temperature.reference.binding.ROOT == binding.SOURCE_ROOT
    assert temperature._implementation.ARMS == ("C1",)
    assert temperature._implementation.DRAW_SEEDS == (101, 103)
    assert temperature.MEAN_TOLERANCES == temperature.reference.MEAN_TOLERANCES
    assert temperature._implementation.components is temperature.reference.components
    assert temperature.original.v32.feedback_gradient is temperature.reference.original.v32.feedback_gradient
    with pytest.raises(ValueError):
        temperature._arm(0.5, "C05")


def test_partial_or_unregistered_checkpoint_refuses_resume(environment):
    e = environment
    bad = e.root / "training/step0895_step"
    bad.mkdir(parents=True)
    with pytest.raises(ValueError, match="partial"):
        training.latest_window_checkpoint(e.root / "training", 894)


def test_new_payload_cannot_cross_actual_points(environment):
    import torch
    e = environment
    rt = SimpleNamespace(torch=torch, v8=SimpleNamespace(
        _tree_digest=lambda value: binding.digest({key: tensor.tolist() for key, tensor in value.items()})))
    directory = runtime.stage_root(e.root, 894, "replay")
    payload = {"gJ": torch.tensor([1., 2.])}
    runtime.save_payload(directory, payload, e.point, "replay", rt)
    restored = runtime.read_payload(directory, e.point, "replay", rt)
    assert torch.equal(restored["gJ"], payload["gJ"])
    with pytest.raises(ValueError, match="another complete state"):
        runtime.read_payload(directory, dict(e.point, id="foreign-point"), "replay", rt)
    with pytest.raises(ValueError, match="cross-point"):
        runtime.read_payload(directory, dict(e.point, step=1192), "replay", rt)


def test_new_T1_receipts_and_strict_joint_replay_use_private_namespace(tmp_path, monkeypatch):
    import test_finance_v63_temperature as fixture
    import torch
    monkeypatch.setattr(fixture, "temperature", temperature)
    provider, condition, cohort = fixture.fixture(2, 1.0)
    assert condition["schema"] == "v70_fresh_continuous_feedback_condition.v1"
    assert condition["probability_contract_id"] != temperature.reference.PROBABILITY_CONTRACT_ID
    with pytest.raises(ValueError, match="outside the registered"):
        temperature.reference.checked_condition(condition)
    draws = {}
    gradient, report = fixture.run(tmp_path / "replay", provider, condition, cohort,
                                   fixture.Backend(), out=draws)
    assert set(draws) == {101, 103}
    assert report["formal_and_draw_checkpoint_atomic"]
    assert report["draw_components"]["mean_check"]["passed"]
    assert torch.allclose(gradient["weight"], (draws[101]["weight"] + draws[103]["weight"]) / 2)


def test_new_joint_response_checkpoint_resume_preserves_real_prefix(tmp_path, monkeypatch):
    import test_finance_v63_temperature as fixture
    monkeypatch.setattr(fixture, "temperature", temperature)
    provider, condition, cohort = fixture.fixture(2, 1.0)
    first = fixture.Backend()
    with pytest.raises(temperature.ReplayPaused):
        fixture.run(tmp_path / "replay", provider, condition, cohort, first,
                    pause_after_response=1)
    assert first.calls == 1
    second, draws = fixture.Backend(start=1), {}
    _, report = fixture.run(tmp_path / "replay", provider, condition, cohort, second, out=draws)
    assert second.calls == 3 and report["restored_completed_responses"] == 1
    assert report["draw_components"]["completed_responses"] == 4


def test_actual_frozen_payload_restore_keeps_execution_plan_despite_window_gates(tmp_path):
    """Original serializer/restorer on tiny CPU tensors, never a model/GPU load."""
    import torch
    from types import FunctionType, MethodType
    from trusted_synthesis.finance_research import v8_training_driver
    assert Path(v8_training_driver.__file__).resolve().is_relative_to(
        Path(binding.install_scientific_paths()["frozen_source_root"]))
    rt = SimpleNamespace(v8=v8_training_driver, torch=torch)
    real = rt.v8.TrainingDriver
    model = torch.nn.Linear(2, 1)
    optimizer = torch.optim.AdamW(model.parameters(), lr=1e-4, weight_decay=0)
    for parameter in model.parameters():
        optimizer.state[parameter] = dict(step=torch.tensor(894.),
            exp_avg=torch.zeros_like(parameter), exp_avg_sq=torch.ones_like(parameter))
    driver = object.__new__(real)
    driver.root, driver.model, driver.optimizer = tmp_path / "actual-native", model, optimizer
    driver.pool = SimpleNamespace(cache_id="tiny-fixed-pool")
    driver.seed, driver.arm = 137, "C-only"
    driver.parameters = dict(model.named_parameters())
    driver.schedule = dict(schedule_sha256="unchanged-original-schedule", batches=[])
    driver.execution_plan = dict(outer_steps=[298, 596, 894, 1192], final_step=1490)
    driver.adapter_binding, driver.base_digest = None, "fixed-base"
    driver.pi = driver.prior = {"task": {"a": 1.0}}
    driver.step_index, driver.outer_done = 894, [298]
    driver.outer_steps, driver.final_step = (298, 596, 894, 1192), 1490
    fixed_rng = dict(cpu=torch.tensor([7, 11], dtype=torch.uint8), cuda=None, fixture_only=True)
    restored_rng = []

    def bind(function, **overrides):
        value = FunctionType(function.__code__, dict(function.__globals__, **overrides),
                             function.__name__, function.__defaults__, function.__closure__)
        value.__kwdefaults__ = function.__kwdefaults__
        return MethodType(value, driver)

    driver._payload = bind(real._payload, _rng=lambda: copy.deepcopy(fixed_rng))
    driver.restore = bind(real.restore, _restore_rng=lambda value: restored_rng.append(value))
    before = driver._payload()
    checkpoint = driver.commit("step", {"cpu_fixture_only": True})
    training.configure_fixed_window(driver, 894)
    assert driver.final_step == 1192 and driver.outer_steps == ()
    assert rt.v8._tree_digest(driver._payload()) == rt.v8._tree_digest(before)
    with torch.no_grad():
        next(iter(driver.parameters.values())).add_(3)
    driver.restore(checkpoint)
    assert rt.v8._tree_digest(driver._payload()) == rt.v8._tree_digest(before)
    assert driver.execution_plan == dict(outer_steps=[298, 596, 894, 1192], final_step=1490)
    assert driver.final_step == 1192 and driver.outer_steps == ()
    assert rt.v8._tree_digest(restored_rng[0]) == rt.v8._tree_digest(fixed_rng)


def test_whole_feedback_payload_reuse_reports_point_dose_not_extra_calls(environment, monkeypatch):
    e = environment
    directory = runtime.stage_root(e.root, 894, "virtual_point")
    (directory / "payload").mkdir(parents=True)
    binding.publish(directory / "payload/record.json", {"fixture": True})
    monkeypatch.setattr(runtime, "load_feedback", lambda *_args: (
        {"point_id": "virtual894", "condition": {"id": "new-T1"}},
        SimpleNamespace(denominator=700, episodes=[SimpleNamespace(actual_model_calls=1)] * 700),
        [1] * 700))
    result = runtime.execute_virtual(e.root, directory, e.point, e.state,
        None, None, None, None, e.rt, None, directory / "attempt")
    assert result["new_feedback_sessions"] == result["total_feedback_sessions"] == 700
    assert result["new_feedback_calls_in_this_attempt"] == 0
    assert result["new_actual_response_calls"] == 0
    assert result["new_feedback_sessions_is_logical_condition_total_not_new_attempt"]
    assert result["cohort_cumulative_response_calls"] == 700
    assert result["completed_payload_reused"]
