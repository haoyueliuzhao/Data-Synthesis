"""Necessary CPU probability controls; no production generation or GPU claims."""

import asyncio
import copy
import hashlib
import json
from types import SimpleNamespace

import pytest
import torch
from test_finance_v19_optimized_replay import tiny
from test_finance_research_providers import Model, Tokenizer, feedback_config

import finqa_v54_temperature as temperature
from trusted_synthesis.finance_research.contracts import Episode, digest
from trusted_synthesis.finance_research.providers import local_model_identity
from trusted_synthesis.finance_research.v8_training_driver import installed_point


@pytest.fixture(autouse=True)
def cpu_threads():
    previous = torch.get_num_threads()
    torch.set_num_threads(1)
    yield
    torch.set_num_threads(previous)


def condition(identity, value=0.5, count=2, *, config=None, production=False):
    config = config or feedback_config(temperature=value)
    return temperature.build_condition(
        identity=identity, temperature=value,
        configs=[config.model_copy(update={"seed": seed}) for seed in (11, 29)],
        task_roster=[{"dataset": "finqa", "task_id": f"q{i}"} for i in range(count)],
        source_manifest_sha256="a" * 64, role_plan_id="test-role-plan",
        cpu_test=not production,
    )


def full_autograd(model, theta, prompt, targets, value):
    ids = torch.tensor([prompt + targets[:-1]])
    with temperature.optimized.legacy.gate.proxy_mode(model, gradient=False):
        output = torch.func.functional_call(
            model, theta, (), dict(input_ids=ids, attention_mask=torch.ones_like(ids),
                                  use_cache=False), strict=False,
        )
        logits = output.logits[0, len(prompt) - 1:].float()
        logps = torch.log_softmax(logits / value, -1).gather(
            -1, torch.tensor(targets)[:, None]
        ).squeeze(-1)
        gradients = torch.autograd.grad(logps.sum(), tuple(theta.values()))
    return logps.detach(), dict(zip(theta, gradients, strict=True))


@pytest.mark.parametrize("value", [1.0, 0.5])
def test_exact_segmented_probability_gradient_against_full_autograd_with_eos(value):
    model, theta = tiny()
    prompt, targets = [2, 3, 5, 7], [1, 4, 6, 8, 10, 12, 13, 14, 15, 9, 11, 16, 17, 2]
    model.generation_config.eos_token_id = 2
    expected, derivative = full_autograd(model, theta, prompt, targets, value)
    session = temperature.ReplaySession(model, theta, temperature=value, condition_id="a" * 64,
                                        profile_id="cpu-math", cpu_test=True)
    actual, gradient, report = session(model, theta, prompt, targets, expected=expected.tolist())
    assert torch.allclose(actual, expected, atol=1e-6, rtol=1e-5)
    for name in theta:
        assert torch.allclose(gradient[name], derivative[name], atol=1e-7, rtol=2e-4)
    assert report["complete_prefix_adjoint_included"]
    assert report["output_tokens"] == len(targets)
    assert report["forward_and_backward_use_same_temperature"]
    assert not report["SFT_mask_used"] and not report["length_normalized"]
    # EOS and the complete generated chain have nonzero gradient contribution.
    _, without_eos = full_autograd(model, theta, prompt, targets[:-1], value)
    assert any(not torch.allclose(gradient[n], without_eos[n], atol=1e-8, rtol=1e-5) for n in theta)
    if value == 0.5:
        _, old = full_autograd(model, theta, prompt, targets, 1.0)
        assert any(not torch.allclose(gradient[n], 2 * old[n], atol=1e-8, rtol=1e-5) for n in theta)
    session.close()


def test_t1_r3_byte_equivalence_and_no_persistent_global_change():
    model, theta = tiny()
    prompt, targets = [2, 3, 5], [1, 4, 6, 8, 10, 12, 13, 14, 2]
    original = temperature.r3.R3Session(model, theta, profile_id="old", cpu_test=True)
    new = temperature.ReplaySession(model, theta, temperature=1.0, condition_id="a" * 64,
                                    profile_id="new", cpu_test=True)
    old_method = temperature.optimized.legacy.SegmentedOperation.forward
    original_softmax = torch.log_softmax
    expected, gradients, _ = original(model, theta, prompt, targets, expected=None)
    actual, derivative, _ = new(model, theta, prompt, targets, expected=expected.tolist())
    assert torch.equal(actual, expected)
    assert all(torch.equal(gradients[n], derivative[n]) for n in theta)
    assert torch.log_softmax is original_softmax
    assert temperature.optimized.legacy.SegmentedOperation.forward is old_method
    original.close()
    new.close()


class TinyTokenizer(Tokenizer):
    def get_vocab(self):
        return {f"token{i}": i for i in range(23)}

    def decode(self, ids, **kwargs):
        return "actual tokens " + ",".join(map(str, ids))


@pytest.mark.parametrize("value", [1.0, 0.5])
def test_real_cpu_hf_sampling_receipts_match_temperature_replay(value):
    model, theta = tiny()
    tokenizer = TinyTokenizer()
    model.generation_config.eos_token_id = tokenizer.eos_token_id
    config = feedback_config(temperature=value, seed=11)
    with installed_point(model, theta) as installed:
        identity = local_model_identity(model, tokenizer, model_id="tiny-qwen", point_id="virtual",
                                        parameter_tensors=installed)
        bound = condition(identity, value, config=config)
        provider = temperature.LocalTorchProvider(model, tokenizer, identity,
                                                  parameter_tensors=installed, condition=bound)
        turn = asyncio.run(provider.chat([{"role": "user", "content": "q0"}], [], config))
        receipt = turn.receipt
        assert receipt.sampling["temperature"] == value
        assert receipt.sampling["feedback_condition_id"] == bound["id"]
        assert receipt.actual_eos == (receipt.raw_generated_token_ids[-1] == tokenizer.eos_token_id)
        session = temperature.ReplaySession(model, installed, temperature=value,
                                            condition_id=bound["id"], profile_id="native-cpu",
                                            cpu_test=True)
        logps, _, _ = session(model, installed, list(receipt.prompt_input_ids),
                              list(receipt.raw_generated_token_ids),
                              expected=list(receipt.sampled_token_logprobs))
        assert torch.allclose(logps, torch.tensor(receipt.sampled_token_logprobs),
                              atol=1e-6, rtol=1e-5)
        session.close()


class SamplingModel(Model):
    def generate(self, **kwargs):
        result = super().generate(**kwargs)
        value = kwargs["generation_config"].temperature
        return SimpleNamespace(sequences=result.sequences,
                               scores=tuple(score / value for score in result.scores))


def sealed_fixture(count=2, value=0.5, production=False):
    model, tokenizer = SamplingModel(), Tokenizer()
    identity = local_model_identity(model, tokenizer, model_id="cpu-mock", point_id="same-point")
    bound = condition(identity, value, count, production=production)
    provider = temperature.LocalTorchProvider(model, tokenizer, identity, condition=bound)
    episodes = []
    for row in bound["ordered_episode_roster"]:
        config = feedback_config(temperature=value, seed=row["seed"])
        turn = asyncio.run(provider.chat([{"role": "user", "content": row["task_id"]}], [], config))
        episodes.append(Episode(
            task_id=row["task_id"], dataset="finqa", public_task_sha256=digest(row["task_id"]),
            config=config, provider=identity, turns=(turn,), tool_events=(), messages=(),
            final_answer="3", stop_reason="final_answer", actual_model_calls=1,
            provider_attempts=1, elapsed_seconds=0.01,
        ))
    cohort = temperature.seal_feedback_cohort(
        episodes, condition=bound, denominator=len(episodes), identity=identity,
        source_manifest_sha256="a" * 64,
        registered_episode_keys=[row["episode_key"] for row in bound["ordered_episode_roster"]],
    )
    return provider, bound, cohort


def test_condition_separates_same_point_temperatures_and_binds_roster_config():
    model, tokenizer = SamplingModel(), Tokenizer()
    identity = local_model_identity(model, tokenizer, model_id="cpu-mock", point_id="same-point")
    low, old = condition(identity), condition(identity, 1.0)
    assert low["id"] != old["id"]
    assert low["identity"] == old["identity"]
    assert low["ordered_episode_roster"][0]["episode_key"] == old["ordered_episode_roster"][0]["episode_key"]
    changed = copy.deepcopy(low)
    changed["temperature"] = 1.0
    with pytest.raises(ValueError, match="identity changed"):
        temperature.checked_condition(changed)
    provider = temperature.LocalTorchProvider(model, tokenizer, identity, condition=low)
    with pytest.raises(ValueError, match="outside its pre-generation condition"):
        asyncio.run(provider.chat([], [], feedback_config(temperature=1.0, seed=11)))
    assert provider.actual_model_calls == 0


def test_seal_rejects_wrong_temperature_receipt_and_wrong_order():
    provider, bound, cohort = sealed_fixture()
    kwargs = dict(condition=bound, denominator=4, identity=provider.identity,
                  source_manifest_sha256="a" * 64,
                  registered_episode_keys=cohort.registered_episode_keys)
    with pytest.raises(ValueError, match="roster|configuration"):
        temperature.seal_feedback_cohort(tuple(reversed(cohort.episodes)), **kwargs)
    episode = cohort.episodes[0]
    turn = episode.turns[0]
    receipt = turn.receipt.model_copy(update={"sampling": dict(turn.receipt.sampling, temperature=1.0)})
    modified = episode.model_copy(update={"turns": (turn.model_copy(update={"receipt": receipt}),)})
    with pytest.raises(ValueError, match="unmodified full-token"):
        temperature.seal_feedback_cohort((modified, *cohort.episodes[1:]), **kwargs)
    binding = temperature.condition_cohort_binding(bound, cohort)
    assert binding["cohort_seal_sha256"] == cohort.seal_sha256
    assert len(binding["receipts"]) == 4


def test_full700_denominator_zero_rewards_full_tokens_and_temperature_checkpoint(tmp_path):
    provider, bound, cohort = sealed_fixture(350, production=True)
    calls = []

    class Backend:
        def __call__(self, model, theta, prompt, targets, *, expected, block_size):
            calls.append(targets)
            return torch.tensor(expected), {"weight": torch.tensor([14.0])}, {}

        def close(self, **kwargs):
            pass

    gradient, report = temperature.feedback_gradient(
        cohort, [1, *([0] * 699)], provider.model, provider.parameters, condition=bound,
        root=tmp_path / "replay", profile_id="fixed700-cpu", cpu_test=True,
        backend_factory=lambda *args: Backend(), rng_restore_source={"id": "test-rng"},
    )
    assert gradient["weight"].item() == pytest.approx(14 / 700)
    assert calls == [[3, 2]]
    assert report["denominator"] == 700
    assert report["accounting"]["zero_reward_trajectories_skipped"] == 699
    state = torch.load(tmp_path / "replay/response000001/state.pt", weights_only=False)
    identity = state["binding"]["backend_identity"]
    assert identity["temperature"] == 0.5 and identity["feedback_condition_id"] == bound["id"]
    assert state["binding"]["gradient_length_normalized"] is False


def test_old_t1_receipts_need_no_rewriting_and_original_seal_matches():
    _, bound, cohort = sealed_fixture(value=1.0)
    old_episodes = []
    for ep in cohort.episodes:
        turn = ep.turns[0]
        sampling = {k: v for k, v in turn.receipt.sampling.items()
                    if k not in ("feedback_condition_id", "probability_contract_id")}
        old_episodes.append(ep.model_copy(update={"turns": (turn.model_copy(update={
            "receipt": turn.receipt.model_copy(update={"sampling": sampling})}),)}))
    kwargs = dict(denominator=4, identity=cohort.identity, source_manifest_sha256="a" * 64,
                  registered_episode_keys=cohort.registered_episode_keys)
    original = temperature.feedback.seal_feedback_cohort(old_episodes, **kwargs)
    current = temperature.seal_feedback_cohort(old_episodes, condition=bound, **kwargs)
    assert current == original


def test_pre_call_boundary_stop_never_starts_a_model_call():
    model, tokenizer = SamplingModel(), Tokenizer()
    identity = local_model_identity(model, tokenizer, model_id="cpu-mock", point_id="same-point")
    bound = condition(identity)
    observed = []

    def stop(event):
        observed.append(event)
        raise RuntimeError("cooperative stop before provider call")

    provider = temperature.LocalTorchProvider(model, tokenizer, identity,
                                              condition=bound, before_call=stop)
    with pytest.raises(RuntimeError, match="before provider call"):
        asyncio.run(provider.chat([], [], feedback_config(temperature=0.5, seed=11)))
    assert provider.actual_model_calls == 0
    assert observed == [dict(phase="before_actual_feedback_call",
                             feedback_condition_id=bound["id"], draw_seed=11, temperature=0.5)]


def test_read_complete_reuses_exact_seals_and_rewards_without_scoring(tmp_path, monkeypatch):
    from trusted_synthesis.finance_research import storage, v6_task

    _, bound, cohort = sealed_fixture(350, production=True)
    root = tmp_path / bound["id"]
    generation = []
    for index in range(2):
        path = root / f"draw{index}/generation_seal/seal.json"
        path.parent.mkdir(parents=True)
        path.write_text(json.dumps({"CPU_fixture_draw": index}))
        generation.append(dict(path=str(path), sha256=hashlib.sha256(path.read_bytes()).hexdigest()))
    temperature._publish(root / "intent", bound)
    temperature._publish(root / "cohort_seal", cohort.model_dump(mode="json"))
    temperature._publish(root / "condition_cohort_binding",
                         temperature.condition_cohort_binding(bound, cohort, generation_seals=generation))
    rewards = [1] + [0] * 699
    temperature._publish(root / "native_rewards", dict(
        condition_id=bound["id"], cohort_seal_sha256=cohort.seal_sha256,
        rewards=rewards, scores=[{"native": {"execution_accuracy": value}} for value in rewards]))
    monkeypatch.setattr(storage, "sealed_episodes", lambda path: (
        None, None, cohort.episodes[350 * int(path.name[-1]):350 * (int(path.name[-1]) + 1)]))

    def forbidden_score(*args, **kwargs):
        raise AssertionError("read-only replay must not score a sealed cohort again")

    monkeypatch.setattr(v6_task, "score_public_reasoning_program", forbidden_score)
    actual, frozen_rewards = temperature.read_complete(root, bound)
    assert actual == cohort and frozen_rewards == rewards


def test_generate_exception_cause_reaches_durable_harness_event_without_retry():
    from trusted_synthesis.finance_research.contracts import PublicTask
    from trusted_synthesis.finance_research.harness import run_episode
    from trusted_synthesis.finance_research.settlement import episode_is_complete

    class FailingModel(Model):
        def generate(self, **kwargs):
            self.calls += 1
            raise RuntimeError("CPU simulated deterministic CUDA matmul workspace failure")

    model, tokenizer = FailingModel(), Tokenizer()
    identity = local_model_identity(model, tokenizer, model_id="cpu-failure-fixture",
                                    point_id="cpu-point")
    bound = condition(identity)
    provider = temperature.LocalTorchProvider(model, tokenizer, identity, condition=bound)
    config = feedback_config(temperature=0.5, seed=11)
    task = PublicTask(dataset="finqa", task_id="q0", version="cpu-fixture",
                      question="CPU fault injection only", sources=())
    events = []
    result = asyncio.run(run_episode(task, provider, config, sink=events.append))
    assert [event["kind"] for event in events] == [
        "episode_started", "model_call_intent", "model_call_failed", "episode_completed",
    ]
    assert provider.actual_model_calls == model.calls == result.actual_model_calls == 1
    assert result.turns == () and result.all_provider_calls_settled is False
    assert not episode_is_complete(result)
    settlement = events[2]["payload"]["settlement"]
    assert settlement["state"] == "unknown" and settlement["actual_model_calls"] == 1
    evidence = settlement["evidence"]
    assert evidence["underlying_cause_available"] is True
    assert evidence["underlying_exception_type"] == "RuntimeError"
    assert evidence["underlying_exception_message"] == (
        "CPU simulated deterministic CUDA matmul workspace failure")
    assert "FailingModel" not in evidence["underlying_exception_message"]
    assert "test_finance_v54_temperature.py" in evidence["underlying_exception_traceback"]
    assert evidence["token_receipt_available"] is False
    assert evidence["feedback_condition_id"] == bound["id"]


def test_unavailable_provider_cause_is_not_invented():
    model, tokenizer = Model(), Tokenizer()
    identity = local_model_identity(model, tokenizer, model_id="cpu-failure-fixture",
                                    point_id="cpu-point")
    bound = condition(identity)
    provider = temperature.LocalTorchProvider(model, tokenizer, identity, condition=bound)

    async def failure_without_cause(*args):
        raise temperature.providers.ProviderCallError(
            "registered CPU fixture rejection", settlement="pre_call_rejected",
            actual_model_calls=0, evidence={"fixture": True})

    provider._temperature_chat = failure_without_cause
    with pytest.raises(temperature.providers.ProviderCallError) as caught:
        asyncio.run(provider.chat([], [], feedback_config(temperature=0.5, seed=11)))
    error = caught.value
    assert error.settlement == "pre_call_rejected" and error.actual_model_calls == 0
    assert error.evidence["underlying_cause_available"] is False
    assert "underlying_exception_message" not in error.evidence
    assert provider.actual_model_calls == model.calls == 0
