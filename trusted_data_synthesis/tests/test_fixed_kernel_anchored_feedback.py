"""New fixed-cohort and zero-term arithmetic controls, no model/effect pilot."""

import importlib
import sys
from pathlib import Path

import pytest
import torch

sys.path.insert(0, str(Path(__file__).parents[1] / "scripts"))
feedback = importlib.import_module("fixed_kernel_anchored_feedback_20260916")
p = feedback.p


def test_registration_is_complete_and_seed_key_is_condition_independent():
    tasks = [dict(task_id="task_" + str(index)) for index in range(180)]
    jobs = feedback.registration(tasks, pool="A", seed=11, round_index=0, stochastic=True)
    assert len(jobs) == 360 and len({(r["task"]["task_id"], r["repeat"]) for r in jobs}) == 360
    assert jobs == feedback.registration(tasks, pool="A", seed=11, round_index=0, stochastic=True)
    assert jobs != feedback.registration(tasks, pool="A", seed=11, round_index=1, stochastic=True)


@pytest.mark.parametrize("positive", [False, True])
def test_zero_terms_keep360_and_positive_error_and_EOS_tokens_are_not_masked(
    tmp_path, monkeypatch, positive
):
    directory = tmp_path / "feedback"
    rows = [dict(job=dict(index=index), session_id=f"session:{index}") for index in range(360)]
    manifest = p.record(
        "anchored_generation_manifest", trajectories=rows, point_id="point:1", stochastic=True
    )
    scoring = p.record(
        "anchored_independent_scoring",
        complete=True,
        denominator=360,
        generation_manifest_id=manifest["id"],
        scores=[
            dict(index=i, session_id=f"session:{i}", Q=int(positive and i == 5)) for i in range(360)
        ],
    )
    p.write_once(directory / "generation_manifest.json", manifest)
    p.write_once(directory / "scoring_report.json", scoring)
    calls = []
    session = dict(
        turns=[
            dict(
                response_index=0,
                protocol_error=True,
                provider_receipt=dict(
                    prompt_input_ids=[1],
                    generated_token_ids=[2, 3],
                    sampled_token_logprobs=[-1.0, -1.0],
                ),
            ),
            dict(
                response_index=1,
                provider_receipt=dict(
                    prompt_input_ids=[1, 2, 3],
                    generated_token_ids=[5, 7],
                    sampled_token_logprobs=[-1.0, -1.0],
                ),
            ),
        ]
    )
    monkeypatch.setattr(feedback, "read_session", lambda *_: session)

    def derivative(model, theta, prompt, tokens, **kwargs):
        calls.append(tokens)
        return (
            torch.zeros(len(tokens)),
            {"weight": torch.tensor([float(sum(tokens))])},
            dict(cached_forward_target_positions=2 * len(tokens)),
        )

    monkeypatch.setattr(feedback.segmented, "segmented_logp", derivative)
    gradient, report = feedback.feedback_gradient(
        tmp_path, directory, None, {"weight": torch.tensor([0.0])}
    )
    assert report["denominator"] == 360
    assert torch.allclose(gradient["weight"], torch.tensor([17 / 360 if positive else 0.0]))
    assert calls == ([[2, 3], [5, 7]] if positive else [])
    assert report["accounting"]["zero_reward_gradient_terms_skipped"] == (359 if positive else 360)
