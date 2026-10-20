"""Necessary CPU/mock controls; no actual Student, GPU, API or science writes."""
from __future__ import annotations

import asyncio
import copy
import json
from pathlib import Path
from types import SimpleNamespace

import finqa_v63_temperature as temperature

import pytest
import torch
from test_finance_research_providers import Model, Tokenizer, feedback_config
from trusted_synthesis.finance_research.contracts import Episode, digest
from trusted_synthesis.finance_research.providers import local_model_identity


@pytest.fixture(autouse=True)
def single_thread():
    previous = torch.get_num_threads()
    torch.set_num_threads(1)
    yield
    torch.set_num_threads(previous)


class MockSamplingModel(Model):
    def generate(self, **kwargs):
        # Existing fully synthetic fixture, not an HF/model sampling test.
        result = super().generate(**kwargs)
        value = kwargs["generation_config"].temperature
        result.scores = tuple(score / value for score in result.scores)
        return result


def fixture(count=10, value=0.5, *, production=False):
    model, tokenizer = MockSamplingModel(), Tokenizer()
    identity = local_model_identity(model, tokenizer, model_id="v63-cpu-mock", point_id="fixed-pre596")
    configs = [feedback_config(temperature=value, seed=seed) for seed in temperature.DRAW_SEEDS]
    condition = temperature.build_condition(
        identity=identity, temperature=value, configs=configs,
        task_roster=[dict(dataset="finqa", task_id=f"q{i}") for i in range(count)],
        source_manifest_sha256="a" * 64, role_plan_id="role", cpu_test=not production)
    provider = temperature.LocalTorchProvider(model, tokenizer, identity, condition=condition)
    episodes = []
    for row in condition["ordered_episode_roster"]:
        config = feedback_config(temperature=value, seed=row["seed"])
        turn = asyncio.run(provider.chat([dict(role="user", content=row["task_id"])], [], config))
        episodes.append(Episode(
            task_id=row["task_id"], dataset="finqa", public_task_sha256=digest(row["task_id"]),
            config=config, provider=identity, turns=(turn,), tool_events=(), messages=(),
            final_answer="3", stop_reason="final_answer", actual_model_calls=1,
            provider_attempts=1, elapsed_seconds=0.01))
    cohort = temperature.seal_feedback_cohort(
        episodes, condition=condition, denominator=len(episodes), identity=identity,
        source_manifest_sha256="a" * 64,
        registered_episode_keys=[row["episode_key"] for row in condition["ordered_episode_roster"]])
    return provider, condition, cohort


class Backend:
    def __init__(self, values=None, start=0, fail=None):
        self.values = values
        self.calls, self.start, self.fail = 0, start, fail
        self.closed = False

    def __call__(self, model, theta, prompt, targets, *, expected, block_size):
        index = self.start + self.calls
        self.calls += 1
        value = self.values[index] if self.values is not None else (index % 7 + 1) / 13
        result = torch.tensor(expected), {"weight": torch.tensor([value])}, {}
        if self.fail == "logp":
            return result[0] + 1, result[1], {}
        if self.fail == "gradient":
            result[1]["weight"].fill_(float("nan"))
        return result

    def close(self, **kwargs):
        self.closed = True


def run(root, provider, condition, cohort, backend, *, rewards=None, out=None, **kwargs):
    return temperature.feedback_gradient(
        cohort, rewards if rewards is not None else [1] * cohort.denominator,
        provider.model, provider.parameters, condition=condition,
        root=root, profile_id="fixed-v63-cpu",
        backend_factory=lambda *_args: backend,
        mean_tolerances=temperature.MEAN_TOLERANCES, draw_components_out=out,
        rng_restore_source={"id": "same-rng"}, cpu_test=True, **kwargs)


def uninstrumented(root, provider, condition, cohort, backend, *, rewards=None, **kwargs):
    compute = temperature.original.optimized.bind_dependencies(
        temperature.original.v32.feedback_gradient,
        seal_feedback_cohort=lambda episodes, **fields: temperature.seal_feedback_cohort(
            episodes, condition=condition, **fields),
        BACKEND_VERSION=temperature.BACKEND_VERSION)
    return compute(
        cohort, rewards if rewards is not None else [1] * cohort.denominator,
        provider.model, provider.parameters, root=root, profile_id="fixed-v63-cpu",
        backend_factory=lambda *_args: backend,
        backend_identity=temperature.backend_identity(
            condition, mean_tolerances=temperature.MEAN_TOLERANCES),
        rng_restore_source={"id": "same-rng"}, cpu_test=True, **kwargs)


def test_new_conditions_bind_temperature_batch_and_draws():
    _, low, _ = fixture(1, 0.5)
    _, high, _ = fixture(1, 1.0)
    assert low["id"] != high["id"]
    assert low["identity"] == high["identity"]
    assert low["feedback_batch"] == high["feedback_batch"] == 1
    assert low["draw_seeds"] == high["draw_seeds"] == [101, 103]
    assert [row["seed"] for row in low["ordered_episode_roster"]] == [101, 103]
    for field, value in (("feedback_batch", 0), ("draw_seeds", [11, 29]), ("arm", "C1")):
        changed = copy.deepcopy(low)
        changed[field] = value
        changed["id"] = digest({k: v for k, v in changed.items() if k != "id"})
        with pytest.raises(ValueError):
            temperature.checked_condition(changed)


@pytest.mark.parametrize("value", [1.0, 0.5])
def test_new_receipts_must_have_condition_even_at_T1(value):
    provider, condition, cohort = fixture(1, value)
    ep = cohort.episodes[0]
    turn = ep.turns[0]
    sampling = {k: v for k, v in turn.receipt.sampling.items()
                if k not in ("feedback_condition_id", "probability_contract_id")}
    changed = ep.model_copy(update={"turns": (turn.model_copy(update={
        "receipt": turn.receipt.model_copy(update={"sampling": sampling})}),)})
    with pytest.raises(ValueError, match="batch1 condition"):
        temperature.seal_feedback_cohort(
            [changed, cohort.episodes[1]], condition=condition, denominator=2,
            identity=provider.identity, source_manifest_sha256="a" * 64,
            registered_episode_keys=cohort.registered_episode_keys)


@pytest.mark.parametrize("value", [1.0, 0.5])
def test_formal_sum_is_bitwise_unchanged_and_draw_means_pass(tmp_path, value):
    provider, condition, cohort = fixture(10, value)
    original_function = temperature.original.v32.feedback_gradient
    original_backend = temperature.original.ReplaySession
    reference, _ = uninstrumented(tmp_path / "reference", provider, condition, cohort, Backend())
    out, monitor = {}, []
    actual, report = run(tmp_path / "joint", provider, condition, cohort, Backend(),
                         out=out, component_monitor=monitor.append)
    assert torch.equal(actual["weight"], reference["weight"])
    assert set(out) == {101, 103}
    assert all(t.device.type == "cpu" for draw in out.values() for t in draw.values())
    assert report["draw_components"]["mean_check"]["passed"]
    assert report["draw_components"]["formal_response_arithmetic_unchanged"]
    assert report["draw_components"]["response_counts"] == {101: 10, 103: 10}
    assert temperature.original.v32.feedback_gradient is original_function
    assert temperature.original.ReplaySession is original_backend
    assert any(row["phase"] == "after_atomic_draw_checkpoint_serialization" for row in monitor)
    assert report["draw_components"]["component_bytes"] == 8


def test_actual_checkpoint_resume_keeps_both_draws_and_does_not_repeat_prefix(tmp_path):
    provider, condition, cohort = fixture()
    reference_out = {}
    reference, _ = run(tmp_path / "whole", provider, condition, cohort, Backend(), out=reference_out)
    first = Backend()
    with pytest.raises(temperature.ReplayPaused) as caught:
        run(tmp_path / "resume", provider, condition, cohort, first, pause_after_response=16)
    assert first.calls == 16 and first.closed
    assert caught.value.checkpoint_record["cursor"] == 16
    saved = torch.load(tmp_path / "resume/response000016/state.pt", weights_only=False)
    assert saved["cursor"] == saved["draw_components"]["cursor"] == 16
    assert saved["draw_components"]["response_counts"] == {101: 10, 103: 6}
    second, out = Backend(start=16), {}
    actual, report = run(tmp_path / "resume", provider, condition, cohort, second, out=out)
    assert second.calls == 4 and second.closed
    assert report["restored_completed_responses"] == 16
    assert torch.equal(actual["weight"], reference["weight"])
    for seed in (101, 103):
        assert torch.equal(out[seed]["weight"], reference_out[seed]["weight"])
    already_done = Backend()
    again, again_report = run(tmp_path / "resume", provider, condition, cohort, already_done, out={})
    assert already_done.calls == 0
    assert torch.equal(again["weight"], actual["weight"])
    assert again_report["restored_completed_responses"] == 20


def test_production700_and_draw350_denominators_include_zero_rewards(tmp_path):
    provider, condition, cohort = fixture(350, production=True)
    rewards = [0] * 700
    rewards[0] = rewards[350] = 1
    out, backend = {}, Backend([14.0, 21.0])
    actual, report = run(tmp_path, provider, condition, cohort, backend, rewards=rewards, out=out)
    reference = torch.zeros(1)
    reference.add_(torch.tensor([14.0]), alpha=1 / 700)
    reference.add_(torch.tensor([21.0]), alpha=1 / 700)
    assert torch.equal(actual["weight"], reference)
    assert out[101]["weight"].item() == pytest.approx(14 / 350)
    assert out[103]["weight"].item() == pytest.approx(21 / 350)
    assert backend.calls == 2
    assert report["accounting"]["zero_reward_trajectories_skipped"] == 698
    assert report["draw_components"]["formal_denominator"] == 700
    assert report["draw_components"]["draw_denominator"] == 350


def test_all_zero_reward_commits_both_zero_components_without_backend(tmp_path):
    provider, condition, cohort = fixture(2)
    backend, out = Backend(), {}
    actual, report = run(tmp_path, provider, condition, cohort, backend,
                         rewards=[0] * 4, out=out)
    assert backend.calls == 0
    assert actual["weight"].item() == out[101]["weight"].item() == out[103]["weight"].item() == 0
    record = json.loads((tmp_path / "response000000/record.json").read_text())
    assert record["formal_and_draws_atomically_committed"]
    assert record["full_replay_complete"]
    assert report["draw_components"]["mean_check"]["relative_L2_error"] is None


@pytest.mark.parametrize("failure", ["logp", "gradient"])
def test_invalid_response_cannot_commit_formal_or_diagnostic_prefix(tmp_path, failure):
    provider, condition, cohort = fixture(1)
    backend = Backend(fail=failure)
    with pytest.raises(ValueError):
        run(tmp_path, provider, condition, cohort, backend, pause_after_response=1)
    assert not list(tmp_path.glob("response*"))
    assert backend.closed


def test_formal_only_checkpoint_rejected_without_replaying_old_gradient(tmp_path):
    provider, condition, cohort = fixture(2)
    with pytest.raises(temperature.ReplayPaused):
        uninstrumented(tmp_path, provider, condition, cohort, Backend(), pause_after_response=1)
    backend = Backend()
    with pytest.raises(ValueError, match="formal-only historical"):
        run(tmp_path, provider, condition, cohort, backend)
    assert backend.calls == 0


def test_component_resource_failure_is_not_hidden_or_committed(tmp_path):
    provider, condition, cohort = fixture(1)

    def monitor(row):
        if row["phase"] == "after_draw_component_accumulation":
            raise RuntimeError("registered RSS hard gate")

    backend = Backend()
    with pytest.raises(RuntimeError, match="RSS hard gate"):
        run(tmp_path, provider, condition, cohort, backend, component_monitor=monitor)
    assert backend.closed
    assert not list(tmp_path.glob("response*"))


def test_wrong_tolerance_is_not_accepted_or_automatically_widened(tmp_path):
    provider, condition, cohort = fixture(1)
    with pytest.raises(ValueError, match="separately registered"):
        temperature.feedback_gradient(
            cohort, [1, 1], provider.model, provider.parameters, condition=condition,
            mean_tolerances={"atol": 1e-3, "rtol": 1e-2, "source": "wider"},
            cpu_test=True, root=tmp_path, profile_id="test",
            backend_factory=lambda *_: Backend(), rng_restore_source={"id": "rng"})
    assert not list(tmp_path.iterdir())


def test_actual_draw_mean_failure_has_nonretryable_diagnostic_type():
    values = {"weight": torch.zeros(1)}
    accumulator = temperature.components.DrawAccumulator(
        values, [], condition_id="c" * 64, denominator=700,
        mean_tolerances=temperature.MEAN_TOLERANCES, cpu_test=True)
    accumulator.draws[101]["weight"].fill_(1.0)
    with pytest.raises(temperature.components.DrawDiagnosticError, match="numerical gate") as caught:
        accumulator.compare(values)
    assert caught.value.automatic_recovery_allowed is False


def test_production_component_monitor_is_mandatory_before_any_replay(tmp_path):
    provider, condition, cohort = fixture(350, production=True)
    with pytest.raises(ValueError, match="production component resource monitor"):
        temperature.feedback_gradient(
            cohort, [0] * 700, provider.model, provider.parameters, condition=condition,
            mean_tolerances=temperature.MEAN_TOLERANCES, root=tmp_path, profile_id="test",
            rng_restore_source={"id": "rng"})
    assert not list(tmp_path.iterdir())


def collector_fixture(tmp_path, monkeypatch, value):
    monkeypatch.setattr(temperature.binding, "ROOT", tmp_path)

    def base_init(self, *, snapshot, role_plan, root, config, model_id, seeds):
        self.snapshot, self.root = Path(snapshot), Path(root)
        self.role_plan, self.config, self.model_id = role_plan, config, model_id
        self.seeds = tuple(seeds)
        self.manifest = {"fixture": "unchanged-material"}
        self.tasks = [SimpleNamespace(dataset="finqa", task_id=f"q{i}") for i in range(350)]
        self.public, self.lineages = self.tasks, []

    monkeypatch.setattr(temperature.HistoricalCollector, "__init__", base_init)
    return temperature.LocalFeedbackCollector(
        arm="C1" if value == 1 else "C05", batch=1,
        snapshot=tmp_path / "snapshot", role_plan={"id": "role"},
        root=tmp_path / "feedback", attempt_root=tmp_path / "attempt/generation",
        config=feedback_config(temperature=value, seed=101), model_id="v63-cpu-mock")


@pytest.mark.parametrize("value", [1.0, 0.5])
def test_collector_uses_new_draws_and_durable_unknown_blocks_without_old_quota(
        tmp_path, monkeypatch, value):
    from trusted_synthesis.finance_research import storage

    collector = collector_fixture(tmp_path, monkeypatch, value)
    prepared, attempts = [], []
    monkeypatch.setattr(storage, "prepare_run",
                        lambda *args, **kwargs: prepared.append(kwargs))

    async def unknown(root, provider, **kwargs):
        attempts.append(kwargs)
        assert provider.condition["feedback_batch"] == 1
        assert provider.condition["draw_seeds"] == [101, 103]
        assert provider.condition["temperature"] == value
        assert provider.recovery_guard is None
        raise temperature.durable.GenerationUnknown("unreturned new call")

    monkeypatch.setattr(temperature.durable, "execute_run_resumable", unknown)
    model, tokenizer = MockSamplingModel(), Tokenizer()
    with pytest.raises(temperature.durable.GenerationUnknown, match="unreturned"):
        collector.collect(model, tokenizer, dict(model.named_parameters()),
                          point_id="fixed-pre596")
    assert len(attempts) == 1 and attempts[0]["inheritance"] is None
    assert prepared[0]["config"].seed == 101
    assert prepared[0]["config"].temperature == value
    assert not list((tmp_path / "feedback").glob("*/native_rewards/record.json"))
    assert model.calls == 0


def test_collector_saved_rewards_return_without_generation_or_rescoring(tmp_path, monkeypatch):
    collector = collector_fixture(tmp_path, monkeypatch, 1.0)
    model, tokenizer = MockSamplingModel(), Tokenizer()
    theta = dict(model.named_parameters())
    identity = local_model_identity(model, tokenizer, model_id="v63-cpu-mock",
                                    point_id="fixed-pre596", parameter_tensors=theta)
    condition = temperature.build_condition(
        identity=identity, temperature=1.0,
        configs=[collector.config.model_copy(update={"seed": seed}) for seed in (101, 103)],
        task_roster=collector.tasks, source_manifest_sha256=digest(collector.manifest),
        role_plan_id="role", arm="C1", batch=1)
    root = collector.root / condition["id"]
    rewards_path = root / "native_rewards/record.json"
    rewards_path.parent.mkdir(parents=True)
    rewards_path.write_text("{}")
    expected = object(), [0] * 700
    reads = []

    def saved(actual_root, actual_condition):
        assert actual_root == root and actual_condition == condition
        reads.append(actual_root)
        return expected

    monkeypatch.setattr(temperature, "read_complete", saved)
    actual = collector.collect(model, tokenizer, theta, point_id="fixed-pre596")
    assert actual == expected
    assert reads == [root] and model.calls == 0
