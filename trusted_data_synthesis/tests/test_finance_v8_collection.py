"""Two-slot real harness/mock-HTTP controls; no external model or real wallet."""

import asyncio
import copy
import json

import pytest
from test_finance_research_datasets import finqa_record
from test_finance_research_probe_provider import Client, value
from test_finance_v8_request_partition import IDS, historical_wallet, partition

from trusted_synthesis.finance_research import storage
from trusted_synthesis.finance_research import v8_collection as collection
from trusted_synthesis.finance_research.contracts import RunConfig
from trusted_synthesis.finance_research.datasets import adapt_finqa


@pytest.fixture
def cohort(tmp_path, monkeypatch):
    ledger, _, _ = historical_wallet(tmp_path)
    partition(ledger)
    raw = finqa_record()
    bundles = adapt_finqa(
        [raw, {**raw, "id": "OTHER/2020/page_1.pdf-1", "filename": "OTHER/2020/page_1.pdf"}],
        split="train",
        revision="synthetic-generation",
    )
    tasks = {b.public.task_id: b.public for b in bundles}
    monkeypatch.setattr(collection, "public_tasks", lambda original: tasks)
    snapshot = tmp_path / "snapshot"
    manifest = storage.import_snapshot(bundles, snapshot, source={"fixture": True})
    config = RunConfig(
        role="sft",
        harness_id="bigfinance-derived-vtdo-v7",
        submission_profile="finqa-public-reasoning-v2",
        max_steps=32,
        max_new_tokens=2048,
        context_limit=1048576,
        temperature=1,
    )
    slots = [
        dict(slot_id=IDS[i], task_id=task_id, slot_index=0, purpose="common_material_candidate")
        for i, task_id in enumerate(tasks)
    ]
    output = tmp_path / "generation"
    output.mkdir()
    plan = collection.bound(
        dict(
            original={},
            id_source="synthetic-two-slot",
            task_ids=list(tasks),
            slots=slots,
            slot_denominator=2,
            task_denominator=2,
            configs_by_task={task_id: config.model_dump(mode="json") for task_id in tasks},
            launch_order=[s["slot_id"] for s in slots],
            concurrency=16,
            budget_database=str(ledger.path),
            snapshot=str(snapshot),
            snapshot_id=manifest["id"],
        )
    )
    return output, plan, ledger


def response(program="subtract(8, 2)"):
    result = value()
    function = result["choices"][0]["message"]["tool_calls"][0]["function"]
    function.update(name="submit_program", arguments=json.dumps({"program": program}))
    return result


def test_first_transport_gate_never_uses_quality_and_all_seal_before_native(cohort, monkeypatch):
    output, plan, ledger = cohort
    client = Client(response("add(8, 2)"))  # Both native wrong; still valid transport.
    private_calls = []
    actual_reader = collection._read_snapshot_rows

    def guarded(*args, **kwargs):
        private_calls.append(args[1])
        assert (output / "generation_seal/record.json").exists()
        return actual_reader(*args, **kwargs)

    monkeypatch.setattr(collection, "_read_snapshot_rows", guarded)
    assert asyncio.run(collection.collect(output, plan, ledger, "fake-memory-key", client=client))
    assert not private_calls and len(client.calls) == 2
    transport = collection.read_json(output / "transport_admission/record.json")
    assert transport["quality_used"] is False and transport["transport_settlement_passed"]
    # Completed resume reads original receipts only, never spends again.
    assert asyncio.run(collection.collect(output, plan, ledger, "fake-memory-key", client=client))
    assert len(client.calls) == 2
    report = collection.score_native_support(output, plan, ledger)
    assert private_calls == ["private.references.jsonl"]
    assert report["phase"] == "KNOWN_ZERO_NATIVE_SUPPORT"
    assert report["native_correct_slots"] == 0 and len(report["zero_support_tasks"]) == 2
    assert all(
        r["Q_native"] is False and r["V_trace"] == "not_assessed_native_ineligible"
        for r in report["rows"]
    )
    assert not report["production_semantic_review_started"] and not report["training_admitted"]
    assert collection.score_native_support(output, plan, ledger) == report


def test_unknown_native_is_not_false_or_a_proven_support_gap(cohort, monkeypatch):
    output, plan, ledger = cohort
    client = Client(response())
    assert asyncio.run(collection.collect(output, plan, ledger, "fake-memory-key", client=client))
    monkeypatch.setattr(
        collection,
        "score_public_reasoning_program",
        lambda bundle, episode: {
            "status": "unknown",
            "reason": "synthetic dependency failure",
            "native": {"execution_accuracy": None, "program_accuracy": None},
        },
    )
    report = collection.score_native_support(output, plan, ledger)
    assert report["phase"] == "NATIVE_SCORING_INCOMPLETE"
    assert report["zero_support_tasks"] == [] and report["native_unknown_slots"] == 2
    assert all(r["Q_native"] is None for r in report["rows"])
    assert all(r["V_trace"] == "not_assessed_native_ineligible" for r in report["rows"])
    assert not report["all_1000_native_support_established"]


def test_unfinished_first_slot_stops_dispatch_keeps_unknown_and_cannot_resume(cohort):
    output, plan, ledger = cohort
    client = Client(failure=TimeoutError("synthetic interrupted request"))
    assert not asyncio.run(
        collection.collect(output, plan, ledger, "fake-memory-key", client=client)
    )
    assert len(client.calls) == 1
    assert not (output / "generation_seal").exists()
    assert ledger.snapshot()["unacknowledged_unknown_requests"] == 1
    with pytest.raises(ValueError, match="unresolved"):
        collection.validate_recovery(output, plan, ledger)
    with pytest.raises(ValueError):
        collection.score_native_support(output, plan, ledger)
    assert len(client.calls) == 1 and not (output / "native_support").exists()


def test_missing_paid_wallet_and_orphan_intent_are_never_new_starts(cohort):
    output, plan, ledger = cohort
    original = copy.deepcopy(plan)
    original["budget_database"] = str(output / "missing.sqlite3")
    with pytest.raises(Exception, match="missing"):
        collection.ledger_for(original)
    directory = collection.slot_directory(output, plan["slots"][0])
    collection.publish(directory / "started", dict(slot=plan["slots"][0], attempt=1))
    with pytest.raises(ValueError, match="incomplete durable slot"):
        collection.validate_recovery(output, plan, ledger)
    assert not (output / "missing.sqlite3").exists()


def test_partial_generation_cannot_open_private_reference(cohort, monkeypatch):
    output, plan, ledger = cohort

    def forbidden(*args, **kwargs):
        raise AssertionError("private reference leaked before whole seal")

    monkeypatch.setattr(collection, "_read_snapshot_rows", forbidden)
    with pytest.raises(ValueError, match="all original 8000"):
        collection.score_native_support(output, plan, ledger)


def test_saved_episode_mutation_blocks_without_a_new_call(cohort):
    output, plan, ledger = cohort
    client = Client(response())
    assert asyncio.run(collection.collect(output, plan, ledger, "fake-memory-key", client=client))
    path = collection.slot_directory(output, plan["slots"][0]) / "episode/episode.json"
    saved = json.loads(path.read_bytes())
    saved["final_program"] = "multiply(8, 2)"
    path.write_text(json.dumps(saved))
    with pytest.raises(ValueError, match="identity changed"):
        collection.validate_recovery(output, plan, ledger)
    assert len(client.calls) == 2


def test_same_process_sealed_handoff_avoids_replaying_all_history_twice(cohort, monkeypatch):
    output, plan, ledger = cohort
    verified = asyncio.run(
        collection.collect(output, plan, ledger, "fake-memory-key", client=Client(response()))
    )

    def duplicated_replay(*args, **kwargs):
        raise AssertionError("the just-verified complete cohort must be reused in this process")

    monkeypatch.setattr(collection, "validate_recovery", duplicated_replay)
    report = collection.score_native_support(output, plan, ledger, _validated_complete=verified)
    assert report["native_correct_slots"] == 2 and report["all_1000_native_support_established"]
    assert not report["production_semantic_review_started"] and not report["training_started"]
