"""Synthetic historical wallet plus real ledger transitions; never the paid DB."""

import json
import sqlite3
from concurrent.futures import ThreadPoolExecutor

import pytest
from test_finance_unknown_abandonment import acknowledge, fixture, table
from test_finance_v6_probe_budget import reserve, settle

from trusted_synthesis.finance_research.contracts import digest, invocation_identity
from trusted_synthesis.finance_research.probe_budget import (
    BudgetUnavailable,
    DuplicateInvocation,
    RequestPartitionError,
    apply_v8_request_partition,
    read_budget_snapshot,
)

IDS = [f"v7-slot:synthetic-{i:04d}" for i in range(8000)]


def historical_wallet(tmp_path):
    ledger, interrupted, hold = fixture(tmp_path, request_cap=258000)
    acknowledge(ledger, interrupted)
    # Bulk copies are explicitly synthetic fixture history, not claimed API calls.
    with sqlite3.connect(ledger.path) as db:
        db.row_factory = sqlite3.Row
        old = dict(db.execute("SELECT * FROM requests WHERE state='SETTLED'").fetchone())
        columns = list(old)
        rows = []
        for index in range(18940):
            coords = invocation_identity(
                dict(run_id=ledger.run_id, episode_id=f"old-synthetic-{index}", attempt_index=1),
                turn_index=0,
            )
            row = {
                **old,
                "invocation_id": coords["invocation_id"],
                "coordinates_json": json.dumps(coords),
            }
            rows.append(tuple(row[k] for k in columns))
        db.executemany(
            f"INSERT INTO requests ({','.join(columns)}) VALUES ({','.join('?' for _ in columns)})",
            rows,
        )
        db.execute(
            "UPDATE counters SET requests=18942,dispatched=18942,spent=?,"
            "prompt_tokens=1894100,hit_tokens=776581,miss_tokens=1117519,completion_tokens=378820",
            (old["settled_microcny"] * 18941,),
        )
    return ledger, interrupted, hold


def partition(ledger, **changes):
    args = dict(
        expected_run_id=ledger.run_id,
        expected_config_sha256=digest(ledger.config),
        partition_id="synthetic-v8-allocation",
        generation_episode_ids=IDS,
        evidence={"user_authorization": "CPU fixture audit authorization"},
    )
    args.update(changes)
    return apply_v8_request_partition(ledger.path, **args)


def test_partition_preserves_wallet_every_row_and_permanent_unknown(tmp_path):
    ledger, iid, held = historical_wallet(tmp_path)
    before = {name: table(ledger.path, name) for name in ("requests", "counters")}
    old = ledger.snapshot()
    record = partition(ledger)
    assert all(table(ledger.path, key) == value for key, value in before.items())
    current = ledger.snapshot()
    assert {k: current[k] for k in old} == old
    assert current["held_microcny"] == held == 2228224
    assert ledger.request_record(iid)["state"] == "UNKNOWN"
    assert ledger.request_record(iid)["usage_json"] is None
    assert record["historical_requests"] == 18942
    assert current["request_partition"]["limits"] == {
        "generation": 220000,
        "technical_review": 108,
        "production_review": 18000,
    }
    assert current["request_partition"]["buffer_spendable"] is False
    assert partition(ledger) == record
    # The instance was opened before registration: no stale-instance bypass.
    with pytest.raises(BudgetUnavailable, match="namespace"):
        reserve(ledger, "old-review-new-call", 16384)
    with pytest.raises(DuplicateInvocation):
        reserve(ledger, "abandoned-original-call", 16384)
    new, _ = reserve(ledger, IDS[0], 2048)
    settle(ledger, new, 20)
    assert ledger.snapshot()["request_partition"]["consumed"]["generation"] == 1
    assert ledger.snapshot()["requests_reserved"] == 18943
    assert partition(ledger) == record
    assert read_budget_snapshot(ledger.path)["config"] == ledger.config


def test_atomic_technical_quota_cannot_borrow_generation_or_buffer(tmp_path):
    ledger, _, _ = historical_wallet(tmp_path)
    partition(ledger)

    def one(index):
        ledger.snapshot()  # Concurrent multi-table reads must use one read transaction.
        try:
            iid, _ = reserve(ledger, f"v8review:{index}", 16384)
            settle(ledger, iid, 20)
            ledger.snapshot()
            return True
        except BudgetUnavailable:
            return False

    with ThreadPoolExecutor(max_workers=8) as pool:
        results = list(pool.map(one, range(116)))
    assert sum(results) == 108
    state = ledger.snapshot()
    assert state["request_partition"]["consumed"]["technical_review"] == 108
    assert state["requests_reserved"] == 18942 + 108
    assert state["pending_requests"] == 0
    for sid in (IDS[0], "v8prod:future-production"):
        iid, _ = reserve(ledger, sid, 2048 if sid in IDS else 16384)
        settle(ledger, iid, 20)
    with pytest.raises(BudgetUnavailable, match="outside"):
        reserve(ledger, "v7-slot:unregistered", 2048)
    with pytest.raises(BudgetUnavailable, match="namespace"):
        reserve(ledger, "buffer:any", 2048)


@pytest.mark.parametrize(
    "failure", ["different_run", "wrong_config", "wrong_slotset", "halt", "pending", "no_authority"]
)
def test_partition_rejects_changes_without_touching_original_wallet(tmp_path, failure):
    ledger, _, _ = historical_wallet(tmp_path)
    changes = {}
    if failure == "different_run":
        changes["expected_run_id"] = "new-wallet"
    elif failure == "wrong_config":
        changes["expected_config_sha256"] = "0" * 64
    elif failure == "wrong_slotset":
        changes["generation_episode_ids"] = IDS[:-1]
    elif failure == "halt":
        ledger.halt(reason="unrelated pause", invocation_id="unrelated")
    elif failure == "pending":
        reserve(ledger, "last-old-pending", 2048)
    else:
        changes["evidence"] = {}
    before = {
        name: table(ledger.path, name) for name in ("requests", "counters", "metadata", "events")
    }
    with pytest.raises(RequestPartitionError):
        partition(ledger, **changes)
    assert all(table(ledger.path, key) == value for key, value in before.items())


def test_partition_does_not_create_missing_ledger_or_clear_later_halt(tmp_path):
    with pytest.raises(RequestPartitionError, match="missing"):
        apply_v8_request_partition(
            tmp_path / "missing",
            expected_run_id="x",
            expected_config_sha256="x",
            partition_id="x",
            generation_episode_ids=IDS,
            evidence={"user_authorization": "fixture"},
        )
    assert not (tmp_path / "missing").exists()
    ledger, _, _ = historical_wallet(tmp_path)
    registered = partition(ledger)
    ledger.halt(reason="later unrelated pause", invocation_id="later")
    assert partition(ledger) == registered
    assert ledger.snapshot()["halt"]["reason"] == "later unrelated pause"
    with pytest.raises(BudgetUnavailable):
        reserve(ledger, IDS[0], 2048)


def test_retry_and_multiple_review_turns_are_not_new_capacity(tmp_path):
    ledger, _, _ = historical_wallet(tmp_path)
    partition(ledger)
    for episode, attempt, turn in ((IDS[0], 2, 0), ("v8review:one", 1, 1)):
        coords = invocation_identity(
            dict(run_id=ledger.run_id, episode_id=episode, attempt_index=attempt), turn_index=turn
        )
        body = dict(model="deepseek-flash", max_tokens=2048, thinking={"type": "disabled"})
        with pytest.raises(BudgetUnavailable):
            ledger.reserve(
                coords["invocation_id"],
                coordinates=coords,
                request=body,
                request_body=json.dumps(body).encode(),
            )
