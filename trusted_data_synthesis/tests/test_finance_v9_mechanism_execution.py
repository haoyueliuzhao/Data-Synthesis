"""Real tiny CPU state/optimizer/short-training with sealed zero-reward controls."""

from fractions import Fraction
from types import SimpleNamespace

import pytest
import torch
from test_finance_research_feedback import episode, seal
from test_finance_research_providers import Model, Tokenizer
from test_finance_v9_conditional_training import TinyModel, material

from trusted_synthesis.finance_research.providers import LocalTorchProvider, local_model_identity
from trusted_synthesis.finance_research.v8_training_driver import installed_point
from trusted_synthesis.finance_research.v9_conditional_training import ConditionalTrainingDriver
from trusted_synthesis.finance_research.v9_mechanism_execution import (
    _registered_update,
    checked_outer,
    evaluation_configs,
    execute_C_reverse,
    execute_N_control,
    same_N_point,
)


class Combined(TinyModel, Model):
    def __init__(self):
        TinyModel.__init__(self)
        self.generation_config = SimpleNamespace(eos_token_id=2)
        self.calls = 0


def make_driver(path, arm):
    model = Combined()
    return ConditionalTrainingDriver(
        model,
        torch.optim.AdamW(model.parameters(), lr=1e-4, weight_decay=0),
        material(7),
        root=path,
        seed=11,
        arm=arm,
    )


def cohort(run, cache):
    def collect(prepared, point_id):
        if point_id not in cache:
            with installed_point(run.model, prepared["theta_bar"]) as theta:
                tokenizer = Tokenizer()
                identity = local_model_identity(
                    run.model,
                    tokenizer,
                    model_id="tiny-mechanism-control",
                    point_id=point_id,
                    parameter_tensors=theta,
                )
                local = LocalTorchProvider(run.model, tokenizer, identity, parameter_tensors=theta)
                cache[point_id] = (seal([episode(local, seed=i) for i in (1, 2)], identity), [0, 0])
        return cache[point_id]

    return collect


def run_main(tmp_path, *, change_full_rng=False):
    shared = make_driver(tmp_path / "shared", "shared")
    shared.run_until(4)
    shared_path = shared.root / "step0004_step"
    cache, runs = {}, {}
    for arm in ("Static", "C-only", "Full"):
        run = make_driver(tmp_path / arm, arm)
        run.restore(shared_path, branch=True)
        if arm != "Static":
            run.outer_update(cpu_control_feedback=cohort(run, cache))
        while run.step_index < 8:
            run.step()
        if arm != "Static":
            if arm == "Full" and change_full_rng:
                torch.rand(1)
            run.outer_update(cpu_control_feedback=cohort(run, cache))
        while run.step_index < 10:
            run.step()
        runs[arm] = run
    return shared_path, runs


def test_actual_C_reverse_uses_same_checkpoint_and_no_new_feedback(tmp_path):
    shared, runs = run_main(tmp_path / "main")
    c = runs["C-only"]
    record, state, actual = checked_outer(c.root / "step0004_outer", production=False)
    assert actual["G"]["weight"].numel() > 0
    assert actual["gJ"]["weight"].count_nonzero() == 0
    assert record["outer_inputs_bytes"] > 0
    result = execute_C_reverse(
        factory=make_driver,
        shared=shared,
        positive_outer=c.root / "step0004_outer",
        static_root=runs["Static"].root,
        positive_root=c.root,
        output=tmp_path / "reverse",
    )
    assert result["actual_extra_training_steps"] == 2
    assert result["end_step"] == 6 and result["new_feedback_sessions"] == 0
    assert result["q_plus"] == state["prior"]
    for task, row in state["prior"].items():
        assert result["q_minus"][task] == {z: float(Fraction(v)) for z, v in row.items()}
    assert result["positive_change"]["mu_weighted"]["TV"] == 0
    assert result["actual_GPU_training"] is False
    with pytest.raises(ValueError, match="production feedback"):
        checked_outer(c.root / "step0004_outer")


@pytest.mark.parametrize("mismatch", [False, True])
def test_N_reuse_requires_real_identity_else_fixed_anchor_one_epoch(tmp_path, mismatch):
    _, runs = run_main(tmp_path / "main", change_full_rng=mismatch)
    c, full = runs["C-only"], runs["Full"]
    c_outer, f_outer = c.root / "step0008_outer", full.root / "step0008_outer"
    comparison = same_N_point(c_outer, f_outer, production=False)
    assert comparison["same_point"] is (not mismatch)
    result = execute_N_control(
        factory=make_driver,
        C_outer=c_outer,
        Full_outer=f_outer,
        C_root=c.root,
        Full_root=full.root,
        output=tmp_path / "N",
    )
    assert result["actual_extra_training_steps"] == (2 if mismatch else 0)
    assert result["end_step"] == 10 and result["new_feedback_sessions"] == 0
    assert result["prior_changed"] is False and result["N_activated"] is False


def test_tampered_outer_tensor_evidence_cannot_be_reused(tmp_path):
    _, runs = run_main(tmp_path / "main")
    path = runs["C-only"].root / "step0008_outer"
    raw = (path / "outer_inputs.pt").read_bytes()
    (path / "outer_inputs.pt").write_bytes(raw + b"tamper")
    with pytest.raises(ValueError, match="evidence bytes"):
        checked_outer(path, production=False)


def test_calibration_config_and_all_three_draws_before_any_reference(tmp_path, monkeypatch):
    from test_finance_research_providers import provider

    from trusted_synthesis.finance_research import storage
    from trusted_synthesis.finance_research import v9_mechanism_execution as mechanism
    from trusted_synthesis.finance_research.v8_training_driver import _publish

    configs = evaluation_configs()
    assert [(c.role, c.temperature, c.seed) for c in configs] == [
        ("calibration", 1.0, 11),
        ("calibration", 1.0, 29),
        ("calibration", 0.0, 20260928),
    ]
    assert all(
        (c.max_steps, c.max_new_tokens, c.context_limit) == (32, 2048, 24576) for c in configs
    )
    tasks = [f"t{i}" for i in range(120)]
    reg = dict(id="registered", calibration_task_keys=tasks, calibration_task_ids=tasks)
    result, reference = dict(id="result"), dict(path="actual-checkpoint")
    root = tmp_path / "point"
    _publish(
        root / "intent",
        mechanism._bound(
            dict(
                checkpoint=reference,
                mechanism_result_id=result["id"],
                identity={"point_id": "actual"},
            )
        ),
    )
    monkeypatch.setattr(
        mechanism, "_point", lambda *args: (reg, {}, None, {}, result, reference, {}, root)
    )
    seen = []
    original = episode(provider())

    def sealed(path):
        index = int(path.name.removeprefix("draw"))
        seen.append(index)
        if index == 2:
            raise FileNotFoundError("last draw not sealed")
        episodes = [
            original.model_copy(update={"task_id": task, "all_provider_calls_settled": True})
            for task in tasks
        ]
        return (
            dict(
                tasks=tasks,
                config=configs[index].model_dump(mode="json"),
                provider={"point_id": "actual"},
            ),
            {"id": str(index)},
            episodes,
        )

    monkeypatch.setattr(storage, "sealed_episodes", sealed)
    monkeypatch.setattr(
        storage,
        "_read_snapshot_rows",
        lambda *args: pytest.fail("private reference read before360"),
    )
    with pytest.raises(FileNotFoundError, match="last draw"):
        mechanism.score_point(tmp_path, 11, "C_direction", "positive")
    assert seen == [0, 1, 2] and not (root / "whole_seal").exists()


def test_same_point_reuses_actual_singleton_RMS_controls():
    from trusted_synthesis.finance_research.v6_distribution import (
        PARAMETERS,
        automatic_update,
        kernel,
    )

    current = {"mixed": {"a": 0.6, "b": 0.4}, "control": {"z": 1.0}}
    prior = {"mixed": {"a": 0.5, "b": 0.5}, "control": {"z": 1.0}}
    C, mu = (
        {"mixed": {"a": -2.0, "b": 3.0}, "control": {"z": 0.0}},
        {"mixed": "1/2", "control": "1/2"},
    )
    actual = dict(pre_state=dict(pi=current, prior=prior), C=C, mu=mu, rewards=[1, 0])
    expected = kernel.anchored_update(
        current, prior, C, mu, control_tasks=["control"], contribution_only=False, **PARAMETERS
    )
    result = _registered_update(actual, "Full")
    assert result == expected
    assert result["pi_next"] != automatic_update(current, prior, C, mu, arm="Full")["pi_next"]
