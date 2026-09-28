"""Durable unknown-call counterexamples; simulated providers, no API/GPU calls."""

from __future__ import annotations

import asyncio
import json
from pathlib import Path

import pytest
from test_finance_research_storage import fixture_bundle, read_events

from trusted_synthesis.finance_research import storage
from trusted_synthesis.finance_research.contracts import (
    ContextLimitError,
    Episode,
    ModelIdentity,
    ModelTurn,
    ProviderCallError,
    RunConfig,
    digest,
)
from trusted_synthesis.finance_research.native_metrics import score_native
from trusted_synthesis.finance_research.planning import build_role_plan
from trusted_synthesis.finance_research.settlement import episode_is_complete


class SimulatedFailureProvider:
    identity = ModelIdentity(backend="scripted", model_id="settlement-counter-fixture")

    def __init__(self, mode):
        self.mode = mode
        self.actual_model_calls = 0
        self.attempts = 0

    async def chat(self, messages, tools, config):
        self.attempts += 1
        if self.mode == "context_pre_call":
            raise ContextLimitError("full original context exceeds registered reservation")
        if self.mode == "local_pre_call_error":
            raise RuntimeError("deterministic pre-call configuration rejection")
        self.actual_model_calls += 1
        if self.mode == "timeout":
            raise TimeoutError("simulated request began but no receipt returned")
        if self.mode == "context_after_call":
            raise ContextLimitError("a late exception is not proof of no request")
        if self.mode in {"service_failure", "counter_conflict"}:
            raise ProviderCallError(
                "simulated explicit HTTP failure response",
                settlement="service_failure",
                actual_model_calls=0 if self.mode == "counter_conflict" else 1,
                evidence={"http_status": 503, "response_received": True, "fixture": True},
            )
        raise AssertionError("unknown fixture mode")


class UnmeteredReturnedProvider:
    identity = ModelIdentity(backend="scripted", model_id="unmetered-return-fixture")

    def __init__(self):
        self.attempts = 0

    async def chat(self, messages, tools, config):
        self.attempts += 1
        return ModelTurn(raw_text="6", provider_metadata={"fixture": True})


def prepare(tmp_path, provider, *, count=2):
    first = fixture_bundle()
    bundles = [first]
    if count == 2:
        task_id = first.public.task_id + ":second-original-task"
        bundles.append(
            first.model_copy(
                update={
                    "public": first.public.model_copy(update={"task_id": task_id}),
                    "reference": first.reference.model_copy(update={"task_id": task_id}),
                    "lineage": first.lineage.model_copy(update={"original_id": task_id}),
                }
            )
        )
    snapshot, run = tmp_path / "snapshot", tmp_path / "run"
    storage.import_snapshot(bundles, snapshot, source={"fixture": True, "real_model_calls": 0})
    plan = build_role_plan(
        [bundle.public for bundle in bundles], [bundle.lineage for bundle in bundles]
    )
    registration = storage.prepare_run(
        snapshot,
        plan,
        run,
        role="test",
        config=RunConfig(role="test", max_steps=2, submission_profile="finqa_program_v1"),
        identity=provider.identity,
    )
    return run, registration, first


def first_episode(run, registration):
    key = registration["episode_keys"][0]
    return Episode.model_validate_json((run / "episodes" / key / "episode.json").read_bytes())


@pytest.mark.parametrize("mode", ["timeout", "context_after_call", "counter_conflict"])
def test_started_without_settlement_is_durable_unknown_and_stops_next_task(tmp_path, mode):
    provider = SimulatedFailureProvider(mode)
    run, registration, bundle = prepare(tmp_path, provider)
    with pytest.raises(storage.UnsettledExecution, match="incomplete provider execution"):
        asyncio.run(storage.execute_run(run, provider))
    episode = first_episode(run, registration)
    assert episode.actual_model_calls == 1 and episode.provider_attempts == 1
    assert episode.turns == () and episode.call_settlements[0].state == "unknown"
    assert not episode.all_provider_calls_settled and not episode_is_complete(episode)
    assert provider.attempts == 1 and not (run / "generation_seal").exists()
    assert not (run / "events" / registration["episode_keys"][1]).exists()
    pending = storage.read_json(
        run / "incomplete" / registration["episode_keys"][0] / "record.json"
    )
    assert pending["new_work_stopped"] and pending["automatic_retry_allowed"] is False
    assert read_events(run)[-1]["kind"] == "episode_completed"
    # A second execute request reads the saved unknown episode, not another sample.
    with pytest.raises(storage.UnsettledExecution):
        asyncio.run(storage.execute_run(run, provider))
    assert provider.attempts == 1
    scored = score_native(
        bundle,
        None,
        submission_profile="finqa_program_v1",
        stop_reason=episode.stop_reason,
        all_provider_calls_settled=episode.all_provider_calls_settled,
    )
    assert scored["status"] == "unknown"
    assert scored["native"]["execution_accuracy"] is None


@pytest.mark.parametrize(
    "mode, state, actual",
    [
        ("service_failure", "service_failure", 1),
        ("local_pre_call_error", "pre_call_rejected", 0),
    ],
)
def test_known_settlement_is_not_a_financial_zero_or_infrastructure_completion(
    tmp_path, mode, state, actual
):
    provider = SimulatedFailureProvider(mode)
    run, registration, bundle = prepare(tmp_path, provider)
    with pytest.raises(storage.UnsettledExecution):
        asyncio.run(storage.execute_run(run, provider))
    episode = first_episode(run, registration)
    assert episode.call_settlements[0].state == state
    assert episode.actual_model_calls == actual and episode.all_provider_calls_settled
    assert episode.stop_reason == "provider_error" and not episode_is_complete(episode)
    assert provider.attempts == 1 and not (run / "generation_seal").exists()
    scored = score_native(
        bundle,
        None,
        submission_profile="finqa_program_v1",
        stop_reason=episode.stop_reason,
        all_provider_calls_settled=True,
    )
    assert scored["status"] == "unknown" and scored["native"]["execution_accuracy"] is None


def test_context_rejected_before_generate_is_a_known_model_terminal_and_native_zero(tmp_path):
    provider = SimulatedFailureProvider("context_pre_call")
    run, registration, _ = prepare(tmp_path, provider)
    seal = asyncio.run(storage.execute_run(run, provider))
    assert seal["complete"] and seal["all_provider_calls_settled"]
    assert provider.attempts == 2 and provider.actual_model_calls == 0
    episode = first_episode(run, registration)
    assert episode.stop_reason == "context_exceeded" and episode_is_complete(episode)
    assert episode.call_settlements[0].state == "pre_call_rejected"
    assert episode.turns == () and episode.actual_model_calls == 0
    report = storage.score_run(run, tmp_path / "score")
    assert report["denominator"] == 2
    assert (
        report["datasets"]["finqa"]["native_metrics"]["execution_accuracy"]["complete_dataset_mean"]
        == 0
    )
    assert all(row["native"]["native"]["execution_accuracy"] == 0 for row in report["results"])


def test_returned_response_without_actual_counter_cannot_claim_settled(tmp_path):
    provider = UnmeteredReturnedProvider()
    run, registration, _ = prepare(tmp_path, provider)
    with pytest.raises(storage.UnsettledExecution):
        asyncio.run(storage.execute_run(run, provider))
    episode = first_episode(run, registration)
    assert len(episode.turns) == 1 and episode.actual_model_calls is None
    assert episode.call_settlements[0].state == "returned"
    assert episode.call_settlements[0].actual_model_calls is None
    assert not episode.all_provider_calls_settled
    assert provider.attempts == 1 and not (run / "generation_seal").exists()


def test_rehashed_forged_complete_seal_cannot_promote_unknown_episode_or_open_gold(
    tmp_path, monkeypatch
):
    provider = SimulatedFailureProvider("timeout")
    run, registration, _ = prepare(tmp_path, provider, count=1)
    with pytest.raises(storage.UnsettledExecution):
        asyncio.run(storage.execute_run(run, provider))
    key = registration["episode_keys"][0]
    path = run / "episodes" / key / "episode.json"
    seal = dict(
        schema="finance_research_generation_seal.v2",
        run_id=registration["id"],
        episodes=[
            dict(key=key, path=str(path.relative_to(run)), sha256=storage._sha(path.read_bytes()))
        ],
        complete=True,
        registered_denominator=1,
        all_provider_calls_settled=True,
        private_references_read=False,
    )
    seal["id"] = digest(seal)
    storage.write_immutable_artifact_directory(
        run / "generation_seal", {"seal.json": storage.encode(seal)}
    )
    original = Path.read_bytes
    opened_private = []

    def read(path):
        if path.name == "private.references.jsonl":
            opened_private.append(path)
        return original(path)

    monkeypatch.setattr(Path, "read_bytes", read)
    with pytest.raises(ValueError, match="cannot promote"):
        storage.score_run(run, tmp_path / "forged_score")
    assert not opened_private and not (tmp_path / "forged_score").exists()
    assert provider.attempts == 1


def test_terminal_event_contains_exact_settlement_and_not_false_completion(tmp_path):
    provider = SimulatedFailureProvider("timeout")
    run, registration, _ = prepare(tmp_path, provider)
    with pytest.raises(storage.UnsettledExecution):
        asyncio.run(storage.execute_run(run, provider))
    events = read_events(run)
    failure = next(row for row in events if row["kind"] == "model_call_failed")
    assert failure["payload"]["settlement"]["state"] == "unknown"
    assert failure["payload"]["settlement"]["actual_model_calls"] == 1
    terminal = events[-1]["payload"]
    assert terminal["all_provider_calls_settled"] is False
    assert terminal["call_settlements"] == [failure["payload"]["settlement"]]
    assert terminal == json.loads(
        (run / "episodes" / registration["episode_keys"][0] / "episode.json").read_bytes()
    )
