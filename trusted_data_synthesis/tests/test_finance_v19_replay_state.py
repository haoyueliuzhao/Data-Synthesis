"""Ordered CPU replay resume, source binding and no-generation fault controls."""

import importlib
import json
import sys
from pathlib import Path

import pytest
import torch
from test_finance_research_feedback import episode, seal
from test_finance_research_providers import provider

from trusted_synthesis.finance_research.feedback import feedback_gradient as original_gradient

sys.path.insert(0, str(Path(__file__).parents[1] / "scripts"))
state = importlib.import_module("finqa_v19_replay_state")


def fixture(count=21):
    local = provider()
    episodes = [episode(local, task=f"q{i}", seed=i + 1) for i in range(count)]
    cohort = seal(episodes, local.identity)
    # Explicit zeros retain the registered denominator and original response order.
    rewards = [0 if i in (3, 19) else 1 for i in range(count)]
    return local, cohort, rewards


class Backend:
    def __init__(self, fail_after=None):
        self.calls, self.fail_after = 0, fail_after

    def __call__(self, model, theta, prompt, targets, *, expected, block_size):
        self.calls += 1
        if self.fail_after is not None and self.calls > self.fail_after:
            raise RuntimeError("injected interruption after durable boundary")
        # Depends only on the actual saved receipt, not this process's call number.
        value = float(sum(prompt) + sum(targets))
        return (
            torch.tensor(expected),
            {"weight": torch.tensor([value])},
            {"cached_forward_target_positions": len(targets) * 2},
        )

    def close(self, **kwargs):
        pass


def run(local, cohort, rewards, root, backend, **kwargs):
    return state.feedback_gradient(
        cohort,
        rewards,
        local.model,
        local.parameters,
        root=root,
        profile_id="same-profile",
        backend_factory=lambda *a: backend,
        cpu_test=True,
        **kwargs,
    )


def test_resume_after_response16_is_bitwise_equal_without_repeating_saved_prefix(tmp_path):
    local, cohort, rewards = fixture()
    baseline_backend = Backend()
    expected, baseline_report = original_gradient(
        cohort, rewards, local.model, local.parameters, replay=baseline_backend
    )
    first = Backend(fail_after=17)
    with pytest.raises(RuntimeError, match="injected interruption"):
        run(local, cohort, rewards, tmp_path, first)
    assert (tmp_path / "response000016/state.pt").is_file()
    second = Backend()
    actual, report = run(local, cohort, rewards, tmp_path, second)
    assert second.calls == sum(rewards) - 16
    assert torch.equal(actual["weight"], expected["weight"])
    assert report["accounting"] == baseline_report["accounting"]
    assert report["denominator"] == 21 and report["restored_completed_responses"] == 16
    assert report["new_sampling_calls"] == 0
    again_backend = Backend(fail_after=0)
    again, again_report = run(local, cohort, rewards, tmp_path, again_backend)
    assert again_backend.calls == 0
    assert torch.equal(again["weight"], expected["weight"])
    assert again_report["restored_completed_responses"] == sum(rewards)


def test_all_zero_still_has_complete_denominator_and_no_backend(tmp_path):
    local, cohort, _ = fixture(3)
    backend = Backend(fail_after=0)
    actual, report = run(local, cohort, [0, 0, 0], tmp_path, backend)
    assert backend.calls == 0 and actual["weight"].item() == 0
    assert (
        report["denominator"] == 3 and report["accounting"]["zero_reward_trajectories_skipped"] == 3
    )
    assert (tmp_path / "response000000/record.json").is_file()


@pytest.mark.parametrize("change", ["profile", "rewards", "bytes", "rng"])
def test_checkpoint_cannot_cross_profile_rewards_or_rng_or_accept_corruption(tmp_path, change):
    local, cohort, rewards = fixture()
    with pytest.raises(RuntimeError):
        run(local, cohort, rewards, tmp_path, Backend(fail_after=16))
    if change == "bytes":
        (tmp_path / "response000016/state.pt").write_bytes(b"changed")
    elif change == "rng":
        torch.rand(1)
    elif change == "rewards":
        rewards = [0, *rewards[1:]]
    if change == "profile":
        with pytest.raises(ValueError, match="another profile"):
            state.feedback_gradient(
                cohort,
                rewards,
                local.model,
                local.parameters,
                root=tmp_path,
                profile_id="different-profile",
                backend_factory=lambda *a: Backend(),
                cpu_test=True,
            )
    else:
        with pytest.raises(ValueError):
            run(local, cohort, rewards, tmp_path, Backend())


def test_unknown_score_never_becomes_zero(tmp_path):
    local, cohort, _ = fixture(3)
    with pytest.raises(ValueError, match="Unknown is not zero"):
        run(local, cohort, [1, None, 0], tmp_path, Backend())
    assert not (tmp_path / "response000000").exists()


def test_failed_response_is_not_checkpointed(tmp_path):
    local, cohort, rewards = fixture(3)
    with pytest.raises(RuntimeError):
        run(local, cohort, rewards, tmp_path, Backend(fail_after=1))
    assert not list(tmp_path.glob("response*"))
    p = json.loads((tmp_path / "progress/status.json").read_bytes())
    assert p["completed_responses"] == 1
