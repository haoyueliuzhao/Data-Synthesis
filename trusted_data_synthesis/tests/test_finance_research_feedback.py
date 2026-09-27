"""Receipt/seal tests and tiny CPU kernel checks; no actual Student generation."""

import asyncio

import pytest
from test_finance_research_providers import feedback_config, provider

from trusted_synthesis.finance_research.contracts import Episode, digest
from trusted_synthesis.finance_research.feedback import (
    episode_key,
    feedback_gradient,
    seal_feedback_cohort,
)
from trusted_synthesis.finance_research.kernel import prepare_virtual_point, update_distribution
from trusted_synthesis.finance_research.providers import parameter_digest

torch = pytest.importorskip("torch")


def episode(local, task="q1", seed=1):
    config = feedback_config(seed=seed)
    turn = asyncio.run(local.chat([{"role": "user", "content": task}], [], config))
    return Episode(
        task_id=task,
        dataset="finqa",
        public_task_sha256=digest(task),
        config=config,
        provider=local.identity,
        turns=(turn,),
        tool_events=(),
        messages=(),
        final_answer="3",
        stop_reason="final_answer",
        actual_model_calls=1,
        provider_attempts=1,
        elapsed_seconds=0.01,
    )


def seal(episodes, identity):
    return seal_feedback_cohort(
        episodes,
        denominator=len(episodes),
        identity=identity,
        source_manifest_sha256="a" * 64,
        registered_episode_keys=[episode_key(ep) for ep in episodes],
    )


def test_full_denominator_zero_skip_and_eos_preserved():
    local = provider()
    episodes = [episode(local, seed=1), episode(local, seed=2)]
    cohort = seal(episodes, local.identity)
    calls = []

    def replay(model, theta, prompt, targets, *, expected, block_size):
        calls.append((prompt, targets, expected, block_size))
        return (
            torch.tensor(expected),
            {"weight": torch.tensor([6.0])},
            {
                "cached_forward_target_positions": 3,
            },
        )

    gJ, report = feedback_gradient(cohort, [1, 0], local.model, local.parameters, replay=replay)
    assert gJ["weight"].item() == 3.0  # Fixed denominator 2, never successful-only average.
    assert len(calls) == 1 and calls[0][1] == [3, 2]
    assert report["denominator"] == 2 and not report["length_normalized"]
    assert report["accounting"]["sampled_tokens_with_parameter_derivative"] == 2
    assert report["accounting"]["zero_reward_trajectories_skipped"] == 1


def test_seal_requires_registered_complete_roster_and_manifest():
    local = provider()
    ep = episode(local)
    with pytest.raises(ValueError, match="manifest"):
        seal_feedback_cohort(
            [ep],
            denominator=1,
            identity=local.identity,
            source_manifest_sha256="",
            registered_episode_keys=[episode_key(ep)],
        )
    with pytest.raises(ValueError, match="registered"):
        seal_feedback_cohort(
            [ep],
            denominator=1,
            identity=local.identity,
            source_manifest_sha256="a" * 64,
            registered_episode_keys=["bad"],
        )
    with pytest.raises(ValueError, match="denominator"):
        seal_feedback_cohort(
            [ep],
            denominator=2,
            identity=local.identity,
            source_manifest_sha256="a" * 64,
            registered_episode_keys=[episode_key(ep)],
        )


@pytest.mark.parametrize("corruption", ["receipt", "point", "role", "text", "failure", "scores"])
def test_feedback_rejects_untrusted_or_incomplete_receipts(corruption):
    local = provider()
    ep = episode(local)
    turn = ep.turns[0]
    if corruption == "receipt":
        turn = turn.model_copy(update={"receipt": None})
    elif corruption == "point":
        turn = turn.model_copy(
            update={
                "receipt": turn.receipt.model_copy(
                    update={"identity": local.identity.model_copy(update={"point_id": "other"})}
                )
            }
        )
    elif corruption == "role":
        ep = ep.model_copy(update={"config": ep.config.model_copy(update={"role": "test"})})
    elif corruption == "text":
        turn = turn.model_copy(update={"raw_text": "edited"})
    elif corruption == "failure":
        ep = ep.model_copy(update={"error": "oom", "stop_reason": "provider_error"})
    elif corruption == "scores":
        turn = turn.model_copy(
            update={"receipt": turn.receipt.model_copy(update={"sampled_token_logprobs": None})}
        )
    ep = ep.model_copy(update={"turns": (turn,)})
    with pytest.raises(ValueError):
        seal([ep], local.identity)


def test_replay_requires_same_theta_full_rewards_and_untampered_seal():
    local = provider()
    cohort = seal([episode(local)], local.identity)
    with pytest.raises(ValueError, match="theta"):
        feedback_gradient(cohort, [1], local.model, {"weight": torch.tensor([1.0])})
    with pytest.raises(ValueError, match="rewards"):
        feedback_gradient(cohort, [], local.model, local.parameters)
    with pytest.raises(ValueError, match="seal"):
        feedback_gradient(
            cohort.model_copy(update={"seal_sha256": "bad"}), [0], local.model, local.parameters
        )


@pytest.mark.parametrize("reason", ["context_exceeded", "no_tool_call", "multiple_tool_calls"])
def test_complete_observed_model_failure_keeps_fixed_denominator(reason):
    local = provider()
    ep = episode(local).model_copy(update={"stop_reason": reason, "error": "observed failure"})
    cohort = seal([ep], local.identity)
    gradient, report = feedback_gradient(cohort, [0], local.model, local.parameters)
    assert gradient["weight"].item() == 0 and report["denominator"] == 1


def test_kernel_reuses_adamw_c_n_pi_without_mutating_live_model():
    parameter = torch.nn.Parameter(torch.tensor([0.5], dtype=torch.float64))
    optimizer = torch.optim.AdamW([parameter], lr=0.01)
    gradients = {
        "q": {
            "a": {"p": torch.tensor([1.0], dtype=torch.float64)},
            "b": {"p": torch.tensor([2.0], dtype=torch.float64)},
        }
    }
    pi, mu = {"q": {"a": 0.5, "b": 0.5}}, {"q": 1.0}
    prepared = prepare_virtual_point({"p": parameter}, optimizer, gradients, pi, mu)
    gJ = {"p": torch.tensor([1.0], dtype=torch.float64)}
    report = {
        "denominator": 7,
        "all_receipts_validated": True,
        "gJ_digest": parameter_digest(gJ),
        "parameter_digest": parameter_digest(prepared["theta_bar"]),
        "accounting": {},
    }
    result = update_distribution(prepared, gradients, gJ, pi, pi, mu, feedback_report=report)
    assert abs(sum(pi["q"][z] * result["C"]["q"][z] for z in pi["q"])) < 1e-12
    assert "N" in result["distribution"]["task_diagnostics"]["q"]
    assert parameter.item() == 0.5 and not optimizer.state
    assert abs(sum(result["distribution"]["pi_next"]["q"].values()) - 1) < 1e-12


def test_zero_feedback_does_not_move_pi_by_novelty():
    parameter = torch.nn.Parameter(torch.tensor([0.5]))
    optimizer = torch.optim.AdamW([parameter], lr=0.01)
    gradients = {"q": {"a": {"p": torch.tensor([1.0])}, "b": {"p": torch.tensor([2.0])}}}
    pi, prior, mu = {"q": {"a": 0.6, "b": 0.4}}, {"q": {"a": 0.5, "b": 0.5}}, {"q": 1.0}
    prepared = prepare_virtual_point({"p": parameter}, optimizer, gradients, pi, mu)
    gJ = {"p": torch.tensor([0.0])}
    report = {
        "denominator": 3,
        "all_receipts_validated": True,
        "gJ_digest": parameter_digest(gJ),
        "parameter_digest": parameter_digest(prepared["theta_bar"]),
        "accounting": {"zero_reward_trajectories_skipped": 3},
    }
    result = update_distribution(prepared, gradients, gJ, pi, prior, mu, feedback_report=report)
    assert result["distribution"]["pi_next"] == pi
    assert result["distribution"]["status"] == "UNINFORMATIVE_FEEDBACK"
