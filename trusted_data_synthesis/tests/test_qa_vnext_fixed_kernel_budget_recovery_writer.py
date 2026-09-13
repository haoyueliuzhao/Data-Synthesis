"""Sixth-purpose writer scheduling controls; synthetic local I/O only."""

import sqlite3
import time
from concurrent.futures import ThreadPoolExecutor

import pytest
from test_qa_vnext_fixed_kernel_budget import FREEZE, create_wallet, first_session
from test_qa_vnext_fixed_kernel_budget import original_wallet as original_wallet
from test_qa_vnext_fixed_kernel_budget import population as population
from test_qa_vnext_fixed_kernel_budget import registry as registry
from test_qa_vnext_fixed_kernel_budget import wallet as wallet

from trusted_synthesis.experiments.finance_qa_vnext_fixed_kernel_value import budget
from trusted_synthesis.experiments.finance_qa_vnext_fixed_kernel_value import protocol as p


def wait_queued(gate, count):
    deadline = time.monotonic() + 3
    while gate.statistics()["queued_operations"] < count:
        assert time.monotonic() < deadline
        time.sleep(0.001)


def test_priority_gate_is_nonpreemptive_FIFO_with_settlement_ahead_of_reserves():
    gate = budget.PriorityWriterGate()
    order = []

    def work(operation, label):
        with gate.enter(operation):
            order.append(label)

    with ThreadPoolExecutor(max_workers=4) as pool:
        with gate.enter("register"):
            futures = []
            for operation, label in (
                ("reserve", "reserve1"),
                ("reserve", "reserve2"),
                ("settle", "settle"),
                ("cancel_unsent", "cancel"),
            ):
                futures.append(pool.submit(work, operation, label))
                wait_queued(gate, len(futures))
        for future in futures:
            future.result(timeout=3)
    assert order == ["settle", "cancel", "reserve1", "reserve2"]
    stats = gate.statistics(include_events=True)
    assert stats["completed_operations"] == 5
    assert stats["maximum_active_write_connections"] == 1
    assert stats["sqlite_lock_errors"] == 0
    assert all(
        a["released_monotonic_ns"] <= b["acquired_monotonic_ns"]
        for a, b in zip(stats["events"], stats["events"][1:], strict=False)
    )


def test_failed_operation_releases_gate_and_records_first_lock_failure():
    gate = budget.PriorityWriterGate()
    with pytest.raises(sqlite3.OperationalError):
        with gate.enter("settle"):
            raise sqlite3.OperationalError("synthetic database is locked")
    with gate.enter("reserve"):
        pass
    stats = gate.statistics(include_events=True)
    assert stats["completed_operations"] == 2
    assert stats["sqlite_lock_errors"] == 1
    assert stats["first_failure"]["operation"] == "settle"
    assert stats["active_write_connections"] == stats["queued_operations"] == 0


def test_same_wallet_instances_share_gate_but_readers_do_not_queue(wallet, registry):
    ledger, _ = wallet
    second = budget.KernelLedger(ledger.path, FREEZE)
    assert budget._writer_gate(ledger.path) is budget._writer_gate(second.path)
    count = ledger.writer_statistics()["completed_operations"]
    with second.connection(readonly=True) as db:
        assert db.execute("SELECT 1").fetchone()[0] == 1
    assert ledger.writer_statistics()["completed_operations"] == count
    with ThreadPoolExecutor(max_workers=2) as pool:
        futures = [
            pool.submit(value.reserve, first_session(registry, i))
            for i, value in enumerate((ledger, second))
        ]
        leases = [future.result() for future in futures]
    for lease in leases:
        second.cancel_unsent(lease["request_id"], "synthetic_no_HTTP")
    stats = ledger.writer_statistics()
    assert stats["maximum_active_write_connections"] == 1 and stats["sqlite_lock_errors"] == 0


def test_recovery_does_not_clear_closed_old_failed_purpose(wallet, registry):
    ledger, before = wallet
    assert budget.PURPOSE == "kernel_recovery_registration"
    assert "kernel_requests" in budget.OLD_RESERVATIONS
    assert "kernel_requests" in before["original_table_names"]
    assert {"kernel_registration", "kernel_fatal", "kernel_finalization"} <= set(
        before["original_metadata_keys"]
    )
    lease = ledger.reserve(first_session(registry))
    ledger.cancel_unsent(lease["request_id"], "synthetic_no_HTTP")
    with ledger.connection(readonly=True) as db:
        assert budget.legacy_snapshot(db, before) == before
        assert db.execute("SELECT value FROM metadata WHERE key='kernel_fatal'").fetchone()[0]


def test_common_balance_is_not_cached_around_an_external_legacy_insert(
    tmp_path, original_wallet, registry, population
):
    prior = p.COMMON_CAP - 5 * p.REQUEST_RESERVATION - p.REQUEST_RESERVATION
    ledger, _ = create_wallet(tmp_path, original_wallet, registry, population, prior=prior)
    # An independent client bypasses this process's writer gate; shared SQL cap
    # guards still see its new charge. No old preexisting row is modified.
    with sqlite3.connect(ledger.path) as db:
        db.execute(
            "INSERT INTO reservations(request_id,state,reserved_tokens,charged_tokens) "
            "VALUES('synthetic_external_client','reserved',1,1)"
        )
    with pytest.raises(budget.BudgetStop, match="six_purpose_cap"):
        ledger.reserve(first_session(registry))
    assert ledger.snapshot()["kernel_conservative_debit"] == 0


def test_small_mixed_shadow_retains_contract_and_reports_serial_writer_metrics(
    tmp_path, original_wallet, registry, population
):
    before = p.sha(original_wallet)
    result = budget.run_shadow_control(
        original_wallet,
        tmp_path / "mixed_shadow",
        registry,
        population,
        FREEZE,
        stress_workers=8,
        rounds=3,
    )
    assert p.sha(original_wallet) == before
    assert result["status"] == "PASS_SYNTHETIC_SHADOW_ONLY"
    assert result["live_API_calls"] == result["live_new_tokens"] == 0
    assert result["shadow_simulated_request_count"] == 24
    assert result["shadow_simulated_usage_tokens"] == 66
    pressure = result["writer_pressure_test"]
    assert pressure["known_simulated_settlements"] == 22
    assert pressure["proven_unsent_cancellations"] == 2
    assert pressure["writer_statistics"]["sqlite_lock_errors"] == 0
    assert pressure["writer_statistics"]["maximum_active_write_connections"] == 1
    assert result["source_legacy_snapshot_before"] == result["source_legacy_snapshot_after"]
