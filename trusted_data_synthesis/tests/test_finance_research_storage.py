"""Small offline durability/barrier checks; all model responses are explicit fixtures."""

from __future__ import annotations

import asyncio
import json
from pathlib import Path

import pytest

from trusted_synthesis.finance_research import storage
from trusted_synthesis.finance_research.contracts import RunConfig
from trusted_synthesis.finance_research.datasets import adapt_finqa
from trusted_synthesis.finance_research.planning import build_role_plan
from trusted_synthesis.finance_research.providers import ScriptedProvider


def fixture_bundle():
    return adapt_finqa(
        [
            {
                "id": "STORAGE_FIXTURE/2020/page_1.pdf-1",
                "filename": "STORAGE_FIXTURE/2020/page_1.pdf",
                "pre_text": ["All figures are USD."],
                "post_text": ["Preserve the entire footer."],
                "table": [["Year", "Revenue"], ["2020", "8"], ["2019", "2"]],
                "qa": {
                    "question": "What is the revenue increase?",
                    "exe_ans": 6,
                    "program": "subtract(8, 2)",
                    "gold_inds": {"table_1": "PRIVATE_ONLY"},
                },
            }
        ],
        split="test",
        revision="synthetic-storage-v1",
    )[0]


@pytest.fixture
def registered(tmp_path):
    bundle = fixture_bundle()
    snapshot, run = tmp_path / "snapshot", tmp_path / "run"
    storage.import_snapshot([bundle], snapshot, source={"fixture": True, "network_calls": 0})
    plan = build_role_plan([bundle.public], [bundle.lineage])
    provider = ScriptedProvider(['{"name":"final_answer","arguments":{"answer":"6"}}'])
    registration = storage.prepare_run(
        snapshot,
        plan,
        run,
        role="test",
        config=RunConfig(role="test", max_steps=2),
        identity=provider.identity,
    )
    return {
        "snapshot": snapshot,
        "run": run,
        "provider": provider,
        "registration": registration,
        "bundle": bundle,
        "plan": plan,
    }


def read_events(run):
    return [
        json.loads(path.read_bytes()) for path in sorted((run / "events").glob("*/*/event.json"))
    ]


def test_generation_does_not_read_even_corrupted_private_reference(
    registered, monkeypatch, tmp_path
):
    private = registered["snapshot"] / "private.references.jsonl"
    private.write_bytes(b"intentionally corrupt private reference; generation must never open me")
    original_read = Path.read_bytes

    def guarded_read(path):
        if path == private:
            raise AssertionError("generation attempted to open a private reference")
        return original_read(path)

    with monkeypatch.context() as guard:
        guard.setattr(Path, "read_bytes", guarded_read)
        seal = asyncio.run(storage.execute_run(registered["run"], registered["provider"]))
    assert seal["complete"] and seal["private_references_read"] is False
    with pytest.raises(ValueError, match="snapshot member changed: private.references"):
        storage.score_run(registered["run"], tmp_path / "must_not_score")


def test_unsealed_generation_cannot_read_gold_or_score(registered, monkeypatch, tmp_path):
    original_read = Path.read_bytes
    opened_private = []

    def guarded_read(path):
        if path.name == "private.references.jsonl":
            opened_private.append(path)
        return original_read(path)

    monkeypatch.setattr(Path, "read_bytes", guarded_read)
    with pytest.raises((FileNotFoundError, ValueError)):
        storage.score_run(registered["run"], tmp_path / "score")
    assert not opened_private


def test_provider_intent_is_on_disk_before_provider_invocation_and_resume_does_not_resample(
    registered,
):
    base = registered["provider"]
    run = registered["run"]

    class IntentInspectingProvider:
        identity = base.identity
        actual_model_calls = 0
        attempts = 0

        async def chat(self, messages, tools, config):
            self.attempts += 1
            events = read_events(run)
            assert events[-1]["kind"] == "model_call_intent"
            assert events[-1]["payload"]["messages"] == messages
            assert events[-1]["payload"]["tools"] == tools
            assert "PRIVATE_ONLY" not in json.dumps(messages)
            return await base.chat(messages, tools, config)

    provider = IntentInspectingProvider()
    first = asyncio.run(storage.execute_run(run, provider))
    event_count = len(read_events(run))
    second = asyncio.run(storage.execute_run(run, provider))
    assert first == second
    assert provider.attempts == 1 and provider.actual_model_calls == 0
    assert len(read_events(run)) == event_count
    assert read_events(run)[-1]["kind"] == "episode_completed"


def test_unsettled_intent_cannot_be_silently_retried(registered):
    episode_key = registered["registration"]["episode_keys"][0]
    sink = storage.EventSink(registered["run"] / "events" / episode_key)
    sink({"kind": "model_call_intent", "step": 0, "payload": {"fixture": "interrupted"}})
    with pytest.raises(ValueError, match="unsettled episode"):
        asyncio.run(storage.execute_run(registered["run"], registered["provider"]))
    assert registered["provider"]._calls == 0
    assert not (registered["run"] / "generation_seal").exists()


@pytest.mark.parametrize(
    "mutation", ["episode_answer", "episode_dataset", "missing_event", "mismatched_event"]
)
def test_preseal_completed_episode_requires_matching_durable_terminal_event_without_recalling_model(
    registered,
    monkeypatch,
    mutation,
):
    original_publish = storage.write_immutable_artifact_directory

    def interrupt_before_seal(directory, payloads):
        if Path(directory).name == "generation_seal":
            raise OSError("fixture crash after completed episode but before generation seal")
        return original_publish(directory, payloads)

    with monkeypatch.context() as interrupted:
        interrupted.setattr(storage, "write_immutable_artifact_directory", interrupt_before_seal)
        with pytest.raises(OSError, match="fixture crash"):
            asyncio.run(storage.execute_run(registered["run"], registered["provider"]))
    assert registered["provider"]._calls == 1
    episode_id = registered["registration"]["episode_keys"][0]
    episode_path = registered["run"] / "episodes" / episode_id / "episode.json"
    terminal_path = sorted((registered["run"] / "events" / episode_id).glob("*/event.json"))[-1]
    assert json.loads(terminal_path.read_bytes())["kind"] == "episode_completed"
    if mutation in {"episode_answer", "episode_dataset"}:
        episode = json.loads(episode_path.read_bytes())
        episode["final_answer" if mutation == "episode_answer" else "dataset"] = "tampered"
        episode_path.write_text(json.dumps(episode))
    elif mutation == "missing_event":
        terminal_path.unlink()
    else:
        terminal = json.loads(terminal_path.read_bytes())
        terminal["payload"]["final_answer"] = "not the saved episode answer"
        terminal_path.write_text(json.dumps(terminal))
    with pytest.raises(ValueError):
        asyncio.run(storage.execute_run(registered["run"], registered["provider"]))
    assert registered["provider"]._calls == 1
    assert not (registered["run"] / "generation_seal").exists()


@pytest.mark.parametrize("mutation", ["role", "config", "source", "hash"])
def test_registration_role_config_source_and_hash_tampering_rejected_before_calls(
    registered, mutation
):
    path = registered["run"] / "run.json"
    data = json.loads(path.read_bytes())
    if mutation == "role":
        data["role"] = "feedback"
    elif mutation == "config":
        data["config"]["max_steps"] += 1
    elif mutation == "source":
        data["snapshot_id"] = "different-snapshot"
    else:
        data["id"] = "altered-hash"
    path.write_text(json.dumps(data))
    with pytest.raises(ValueError, match="registration identity"):
        asyncio.run(storage.execute_run(registered["run"], registered["provider"]))
    assert registered["provider"]._calls == 0


def test_snapshot_member_or_runtime_changes_rejected_before_calls(registered, monkeypatch):
    original_binding = storage.runtime_binding()
    monkeypatch.setattr(
        storage, "runtime_binding", lambda: {**original_binding, "changed.py": "different"}
    )
    with pytest.raises(ValueError, match="runtime bytes changed"):
        asyncio.run(storage.execute_run(registered["run"], registered["provider"]))
    monkeypatch.undo()
    path = registered["snapshot"] / "public.jsonl"
    path.write_bytes(path.read_bytes() + b" ")
    with pytest.raises(ValueError, match="snapshot member changed: public"):
        asyncio.run(storage.execute_run(registered["run"], registered["provider"]))
    assert registered["provider"]._calls == 0


def test_registered_identity_and_config_role_cannot_drift(registered, tmp_path):
    provider = ScriptedProvider([], model_id="different-fixture")
    with pytest.raises(ValueError, match="registered model"):
        asyncio.run(storage.execute_run(registered["run"], provider))
    with pytest.raises(ValueError, match="config role"):
        storage.prepare_run(
            registered["snapshot"],
            registered["plan"],
            tmp_path / "bad-role",
            role="test",
            config=RunConfig(role="calibration"),
            identity=registered["provider"].identity,
        )


def test_sealed_episode_bytes_cannot_be_changed_then_scored(registered, tmp_path):
    seal = asyncio.run(storage.execute_run(registered["run"], registered["provider"]))
    episode_file = registered["run"] / seal["episodes"][0]["path"]
    episode = json.loads(episode_file.read_bytes())
    episode["final_answer"] = "100"
    episode_file.write_text(json.dumps(episode))
    with pytest.raises(ValueError, match="sealed episode bytes changed"):
        storage.score_run(registered["run"], tmp_path / "tampered-score")


def test_score_separates_native_diagnostic_and_unknown_trajectory_without_completepass(
    registered, tmp_path
):
    asyncio.run(storage.execute_run(registered["run"], registered["provider"]))
    report = storage.score_run(registered["run"], tmp_path / "score")
    assert report["fixture_only"] and not report["real_model_execution"]
    assert not report["training_value_claimed"] and report["new_API_calls_for_scoring"] == 0
    assert report["no_pooled_cross_dataset_finance_score"]
    row = report["results"][0]
    assert row["native"]["derived"]["exact_final_answer_match"] == 1.0
    assert row["native"]["native"]["execution_accuracy"] is None
    assert row["trajectory"]["complete_semantic_support"] == "unknown"
    assert row["trajectory"]["native_answer_correctness_is_not_CompletePass"] is True
    assert "CompletePass" not in row["native"]["derived"]
    assert row["trajectory"]["actual_model_calls"] == 0


def test_registration_output_is_immutable(registered):
    with pytest.raises(FileExistsError):
        storage.prepare_run(
            registered["snapshot"],
            registered["plan"],
            registered["run"],
            role="test",
            config=RunConfig(role="test", max_steps=2),
            identity=registered["provider"].identity,
        )
