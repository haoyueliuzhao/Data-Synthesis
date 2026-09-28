"""Temporary mocked HTTP artifacts only; no live network, credentials or model."""

import asyncio
import hashlib
import json
import shutil
import sqlite3
from dataclasses import asdict

import pytest
from test_finance_research_probe_budget import sheet
from test_finance_research_probe_provider import Client, config, provider, value

from trusted_synthesis.finance_research.contracts import (
    PublicSource,
    PublicTask,
    digest,
    invocation_identity,
)
from trusted_synthesis.finance_research.harness import run_episode
from trusted_synthesis.finance_research.probe_budget import ProbeBudget
from trusted_synthesis.finance_research.probe_recovery import (
    ProbeRecoveryError,
    validate_ledger_recovery,
)
from trusted_synthesis.finance_research.storage import encode


def write(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(encode(value))


@pytest.fixture
def evidence(tmp_path):
    output = tmp_path / "inventory"
    output.mkdir()
    slot = {"slot_id": "finqa_probe_slot:" + "a" * 64, "task_id": "fixture", "slot_index": 0}
    plan = {
        "id": "registered-inventory-fixture",
        "price_sheet": asdict(sheet()),
        "inventory": {"slots": [slot], "slot_config": config().model_dump(mode="json")},
    }
    ledger = ProbeBudget(
        output / "budget.sqlite3", run_id=plan["id"], price_sheet=sheet(), max_output_tokens=2048
    )
    initial_database = ledger.path.read_bytes()  # Before any mocked paid requests.
    responses = [
        ("read_source", {"source_id": "table:0"}),
        (
            "calculate",
            {
                "expression": "a-b",
                "variables": {"a": "prev:r1.output.content.1.1", "b": "prev:r1.output.content.1.2"},
            },
        ),
        (
            "final_answer",
            {"answer": "prev:r2.output.result", "scale": "", "program": "subtract(120, 90)"},
        ),
    ]

    class ChainClient(Client):
        async def post(self, url, **kwargs):
            index = len(self.calls)
            name, arguments = responses[index]
            self.response = value(id=f"fixture-response-{index}")
            self.response["choices"][0]["message"]["tool_calls"] = [
                {
                    "id": f"tool-{index}",
                    "type": "function",
                    "function": {"name": name, "arguments": json.dumps(arguments)},
                }
            ]
            return await super().post(url, **kwargs)

    task = PublicTask(
        dataset="finqa",
        task_id="fixture",
        question="Revenue increase?",
        version="fixture",
        sources=(
            PublicSource(
                source_id="table:0",
                kind="table",
                locator="fixture",
                content=[["metric", "current", "prior"], ["Revenue", "120", "90"]],
            ),
        ),
    )
    episode = asyncio.run(
        run_episode(
            task,
            provider(ledger, ChainClient(), slot["slot_id"]),
            config(),
            invocation_context={
                "run_id": plan["id"],
                "episode_id": slot["slot_id"],
                "attempt_index": 1,
            },
        )
    )
    assert episode.stop_reason == "final_answer" and episode.actual_model_calls == 3
    directory = output / "slots" / slot["slot_id"].split(":", 1)[1]
    path = directory / "episode/episode.json"
    write(path, episode.model_dump(mode="json"))
    outcome = {
        "status": "COMPLETE",
        "slot": slot,
        "episode_path": str(path),
        "episode_file_sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
        "episode_sha256": digest(episode),
        "actual_model_calls": 3,
        "all_provider_calls_settled": True,
        "stop_reason": episode.stop_reason,
    }
    write(directory / "outcome/record.json", outcome)
    return {
        "output": output,
        "plan": plan,
        "ledger": ledger,
        "initial_database": initial_database,
        "completed": {slot["slot_id"]: outcome},
        "episode": episode,
        "episode_path": path,
    }


def test_fresh_output_does_not_create_any_budget_database(tmp_path):
    assert validate_ledger_recovery(tmp_path, {}) is None
    assert not (tmp_path / "budget.sqlite3").exists()


def test_valid_real_provider_mock_episode_and_ledger_conserve_cost_read_only(evidence):
    ledger = evidence["ledger"]
    before = hashlib.sha256(ledger.path.read_bytes()).hexdigest()
    result = validate_ledger_recovery(evidence["output"], evidence["plan"], evidence["completed"])
    assert result["completed_slots"] == result["registered_slots"] == 1
    assert result["settled_requests"] == 3
    assert result["settled_peak_tariff_upper_bound_microcny"] == 840
    assert result["all_paid_calls_bound_to_completed_slots"] and result["read_only"]
    assert hashlib.sha256(ledger.path.read_bytes()).hexdigest() == before


def test_missing_sqlite_in_restored_slot_tree_cannot_reset_the_budget(evidence, tmp_path):
    restored = tmp_path / "restored_without_sqlite"
    shutil.copytree(evidence["output"] / "slots", restored / "slots")
    with pytest.raises(ProbeRecoveryError, match="never reset paid cost"):
        validate_ledger_recovery(restored, evidence["plan"])
    assert not (restored / "budget.sqlite3").exists()


def test_pre_request_sqlite_restoration_is_detected_even_when_episodes_are_intact(evidence):
    # Simulates restoring a stale pre-payment DB only in this temporary fixture.
    evidence["ledger"].path.write_bytes(evidence["initial_database"])
    with pytest.raises(ProbeRecoveryError, match="no corresponding paid ledger row"):
        validate_ledger_recovery(evidence["output"], evidence["plan"])


@pytest.mark.parametrize(
    "change,expected",
    [
        ("UPDATE counters SET spent=spent-1 WHERE singleton=1", "counters"),
        ("UPDATE requests SET request_body=x'7b7d' WHERE rowid=1", "request bytes/hash"),
        ("UPDATE requests SET response_body=x'7b7d' WHERE rowid=1", "response bytes/hash"),
        ("UPDATE requests SET settled_microcny=0 WHERE rowid=1", "amount/reservation"),
    ],
)
def test_inconsistent_ledger_bytes_or_cost_are_blocking(evidence, change, expected):
    with sqlite3.connect(evidence["ledger"].path) as db:
        db.execute(change)
    with pytest.raises(ProbeRecoveryError, match=expected):
        validate_ledger_recovery(evidence["output"], evidence["plan"])


def test_paid_call_without_a_completed_slot_is_not_silently_ignored(evidence):
    ledger = evidence["ledger"]
    asyncio.run(provider(ledger, Client(), "orphan-slot").chat([], [], config()))
    with pytest.raises(ProbeRecoveryError, match="not conserved"):
        validate_ledger_recovery(evidence["output"], evidence["plan"])


def test_pending_request_blocks_recovery_without_clearing_its_reservation(evidence):
    ledger = evidence["ledger"]
    coords = invocation_identity(
        {"run_id": ledger.run_id, "episode_id": "pending-slot", "attempt_index": 1}, turn_index=0
    )
    body = {"model": "deepseek-flash", "thinking": {"type": "disabled"}, "max_tokens": 2048}
    ledger.reserve(
        coords["invocation_id"],
        coordinates=coords,
        request=body,
        request_body=json.dumps(body).encode(),
    )
    ledger.mark_dispatched(coords["invocation_id"])
    before = ledger.snapshot()
    with pytest.raises(ProbeRecoveryError, match="pending/unknown"):
        validate_ledger_recovery(evidence["output"], evidence["plan"])
    assert ledger.snapshot() == before


def test_generation_seal_must_retain_the_actual_durable_outcomes(evidence):
    root, plan = evidence["output"], evidence["plan"]
    row = dict(next(iter(evidence["completed"].values())))
    row["episode_file_sha256"] = "0" * 64
    seal = {"protocol_id": plan["id"], "complete": True, "denominator": 1, "slots": [row]}
    seal["id"] = digest(seal)
    write(root / "generation_seal/record.json", seal)
    with pytest.raises(ProbeRecoveryError, match="generation seal"):
        validate_ledger_recovery(root, plan)
