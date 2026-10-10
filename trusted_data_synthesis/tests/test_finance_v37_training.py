"""CPU-only production commit/step control tests, not GPU equivalence claims."""

import copy
import hashlib
import importlib
import json
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest

sys.path.insert(0, str(Path(__file__).parents[1] / "scripts"))
subject = importlib.import_module("finqa_v37_training")


def digest(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True).encode()).hexdigest()


@pytest.fixture
def example(tmp_path):
    state = dict(
        seed=137,
        arm="Full",
        step=1192,
        outer_done=[298, 596, 894],
        pi={"t": {"a": 0.4, "b": 0.6}},
        prior={"t": {"a": 0.5, "b": 0.5}},
        parameters={"w": [1.0]},
        optimizer={"step": 1192},
        rng={"python": 123},
        buffers={},
        schedule={"id": "fixed"},
    )

    class Driver:
        def __init__(self):
            self.root = tmp_path / "arm/training"
            self.seed, self.arm, self.step_index = 137, "Full", 1192
            self.outer_done, self.pi = (
                copy.deepcopy(state["outer_done"]),
                copy.deepcopy(state["pi"]),
            )
            self.pool = SimpleNamespace(
                _manifest=SimpleNamespace(registration=SimpleNamespace(mu={"t": 1}))
            )
            self.outer_steps, self.final_step = (298, 596, 894, 1192), 1490
            self.tainted, self.commits, self.steps = False, [], 0

        def _payload(self):
            return copy.deepcopy(
                state | dict(step=self.step_index, pi=self.pi, outer_done=self.outer_done)
            )

        def commit(self, phase, evidence, *, outer_inputs):
            destination = self.root / f"step{self.step_index:04d}_{phase}"
            destination.mkdir(parents=True)
            self.commits.append(dict(phase=phase, evidence=evidence, outer_inputs=outer_inputs))
            return destination

        def step(self):
            assert self.step_index not in self.outer_steps or self.step_index in self.outer_done
            self.step_index += 1
            self.steps += 1

    driver = Driver()
    runtime = SimpleNamespace(
        v8=SimpleNamespace(_tree_digest=digest, parameter_digest=digest, PARAMETERS={"b": 0.2})
    )
    context = dict(
        id="context",
        seed=137,
        arm="Full",
        step=1192,
        due_outer=True,
        arm_root=str(tmp_path / "arm"),
        pre_state_digest=digest(state),
        branch=dict(contribution_only=False, b_N=0.2, parameters={"b": 0.2}),
        feedback=dict(mode="sealed_existing", expected_point_id="actual-point"),
        training_stop_step=1193,
    )
    values = dict(
        schema="v9_real_outer_inputs.v1",
        pre_state=state,
        actual_tensors_saved=True,
        mu={"t": 1},
        q_next={"t": {"a": 0.3, "b": 0.7}},
        C={"t": {"a": 0.1, "b": -0.1}},
        feedback_seal=dict(denominator=700, seal_sha256="seal"),
        rewards=[1] * 700,
        point_id="actual-point",
        G={"w": 2},
        theta_bar={"w": 3},
        gJ={"w": 4},
        pullback={"w": 5},
    )
    evidence = dict(
        distribution=dict(pi_next=copy.deepcopy(values["q_next"])),
        C=values["C"],
        actual_feedback_denominator=700,
        feedback_seal_sha256="seal",
        population_gradient_digest=digest(values["G"]),
        actual_virtual_theta_digest=digest(values["theta_bar"]),
        feedback_gradient_digest=digest(values["gJ"]),
        pullback_digest=digest(values["pullback"]),
    )
    monitor = SimpleNamespace(check_stop=lambda *a, **k: None, clear_unused=lambda *a: None)
    return SimpleNamespace(
        context=context,
        driver=driver,
        rt=runtime,
        inputs=values,
        evidence=evidence,
        monitor=monitor,
    )


def test_actual_outer_committed_once_and_next_real_step_counts(example):
    f = example
    result = subject.execute_training(
        f.context,
        f.driver.root,
        f.driver,
        f.rt,
        f.monitor,
        lambda: False,
        outer_inputs=f.inputs,
        evidence=f.evidence,
    )
    assert len(f.driver.commits) == 1
    assert f.driver.steps == result["actual_optimizer_steps"] == 1
    assert result["outer_committed"] and result["first_sft_after_outer"].endswith("step1193_step")
    assert result["feedback_calls"] == 0
    assert f.driver.pi == f.inputs["q_next"]
    assert f.driver.outer_done == [298, 596, 894, 1192]


@pytest.mark.parametrize(
    "bad", ["rng", "point", "Full_branch", "tensor", "denominator", "missing_reward"]
)
def test_bad_payload_never_commits_or_updates(example, bad):
    f = example
    if bad == "rng":
        f.inputs["pre_state"]["rng"] = {"python": 999}
    elif bad == "point":
        f.inputs["point_id"] = "reference-point298"
    elif bad == "Full_branch":
        f.context["branch"]["contribution_only"] = True
    elif bad == "tensor":
        f.inputs["gJ"]["w"] = 99
    elif bad == "denominator":
        f.inputs["feedback_seal"]["denominator"] = 699
    else:
        f.inputs["rewards"][0] = None
    with pytest.raises(ValueError):
        subject.commit_actual_outer(f.context, f.driver, f.rt, f.inputs, f.evidence)
    assert not f.driver.commits and f.driver.steps == 0


def test_existing_outer_is_not_silently_recommitted(example):
    f = example
    (f.driver.root / "step1192_outer").mkdir(parents=True)
    with pytest.raises(ValueError, match="duplicate commit"):
        subject.commit_actual_outer(f.context, f.driver, f.rt, f.inputs, f.evidence)


def test_c_only_branch_keeps_zero_n(example):
    f = example
    f.driver.arm = f.context["arm"] = f.inputs["pre_state"]["arm"] = "C-only"
    f.context["branch"].update(contribution_only=True, b_N=0)
    f.context["pre_state_digest"] = digest(f.inputs["pre_state"])
    subject.commit_actual_outer(f.context, f.driver, f.rt, f.inputs, f.evidence)
    assert len(f.driver.commits) == 1


def test_segment_cannot_cross_an_uncommitted_outer(example):
    f = example
    f.driver.step_index = f.context["step"] = 419
    f.driver.outer_done = [298]
    f.context["pre_state_digest"] = digest(f.driver._payload())
    f.context["due_outer"] = False
    f.context["training_stop_step"] = 597
    with pytest.raises(ValueError, match="next original outer"):
        subject.execute_training(f.context, f.driver.root, f.driver, f.rt, f.monitor, lambda: False)
    assert f.driver.steps == 0


def test_plain_sft_stops_at_next_scheduled_outer(example):
    f = example
    f.driver.step_index = f.context["step"] = 419
    f.driver.outer_done = [298]
    f.context["pre_state_digest"] = digest(f.driver._payload())
    f.context["due_outer"] = False
    f.context.pop("training_stop_step")
    result = subject.execute_training(
        f.context, f.driver.root, f.driver, f.rt, f.monitor, lambda: False
    )
    assert result["committed_step"] == result["next_due_outer"] == 596
    assert result["actual_optimizer_steps"] == 177 and not f.driver.commits
