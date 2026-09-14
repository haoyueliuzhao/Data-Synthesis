"""Small synthetic controls for the prospective completion-only purpose."""

import json
import sqlite3
from concurrent.futures import ThreadPoolExecutor

import pytest

from trusted_synthesis.experiments.finance_qa_vnext_fixed_kernel_value import budget as parent
from trusted_synthesis.experiments.finance_qa_vnext_fixed_kernel_value import completion_budget as b
from trusted_synthesis.experiments.finance_qa_vnext_fixed_kernel_value import protocol as p

OLD_FREEZE, NEW_FREEZE = "synthetic_closed_recovery", "synthetic_prospective_completion"
PARENT_REPORT = "synthetic_closed_report"


def make_closed_wallet(path):
    """272 known-safe slots, 404 settled prefixes, five charged old unknowns."""
    slots = []
    with sqlite3.connect(path) as db:
        db.execute("CREATE TABLE metadata(key TEXT PRIMARY KEY,value TEXT NOT NULL)")
        db.execute("CREATE TABLE prior_debits(name TEXT PRIMARY KEY,tokens INTEGER NOT NULL)")
        db.execute("INSERT INTO prior_debits VALUES('historical_cost',1000)")
        final = p.record(
            "kernel_budget_finalization",
            freeze_id=OLD_FREEZE,
            report_id=PARENT_REPORT,
            purpose_closed=True,
            old_purposes_not_reopened=True,
        )
        metadata = {
            "policy": json.dumps({"stage_id": p.OWNER, "common_new_experiment_cap": b.COMMON_CAP}),
            parent.FATAL: "old_budget_cap_stop_preserved",
            parent.FINAL: p.encode(final).decode(),
        }
        db.executemany("INSERT INTO metadata VALUES(?,?)", list(metadata.items()))
        for table in parent.ALL_RESERVATIONS:
            db.execute(f"""CREATE TABLE {table}(
              request_id TEXT PRIMARY KEY, session_id TEXT, attempt INTEGER, state TEXT,
              reserved_tokens INTEGER, charged_tokens INTEGER, prompt_tokens INTEGER,
              completion_tokens INTEGER, reported_total_tokens INTEGER, http_success INTEGER,
              response_model TEXT, outcome TEXT, created_at TEXT)""")
            if table != "kernel_recovery_requests":
                db.execute(
                    f"INSERT INTO "
                    f"{table}(request_id,state,reserved_tokens,charged_tokens) "
                    f"VALUES(?,'usage_unknown',115712,115712)",
                    ("old_unknown_" + table,),
                )
        db.execute(
            "CREATE TABLE kernel_recovery_sessions(session_id TEXT PRIMARY KEY, "
            "registered_json TEXT,state TEXT,terminal TEXT)"
        )
        for index in range(p.SESSION_CAP):
            sid = f"original_slot_{index}"
            reg = {"session_id": sid, "ordinal": index, "identity": {"original": index}}
            terminal = "first_final"
            if index < b.SESSION_CAP:
                aborted = index < 121
                count = 4 if index < 41 else 3 if aborted else 0
                previous = [
                    f"original_request_{index}_{attempt}" for attempt in range(1, count + 1)
                ]
                slot = dict(
                    registered_session=reg,
                    parent_status="budget_aborted" if aborted else "not_run",
                    prefix_request_ids=previous,
                )
                slots.append(slot)
                terminal = (
                    "fatal_provider_or_budget_stop"
                    if aborted
                    else "not_requested_or_failed_after_global_stop"
                )
                for attempt, request_id in enumerate(previous, 1):
                    db.execute(
                        "INSERT INTO kernel_recovery_requests "
                        "VALUES(?,?,?,'settled',115712,3,2,1,3,1,?,"
                        "'public_response_received','synthetic_time')",
                        (request_id, sid, attempt, p.MODEL),
                    )
            db.execute(
                "INSERT INTO kernel_recovery_sessions VALUES(?,?,'finished',?)",
                (sid, p.encode(reg).decode(), terminal),
            )
    manifest = p.record(
        "kernel_completion_manifest",
        original_freeze_id=OLD_FREEZE,
        parent_report_id=PARENT_REPORT,
        authorization_id="synthetic_user_budget_increase",
        parent_registry_id="synthetic_original_registry",
        slots=slots,
    )
    return manifest


@pytest.fixture
def wallet(tmp_path):
    path = tmp_path / "completion_shadow.sqlite3"
    manifest = make_closed_wallet(path)
    ledger = b.CompletionLedger(path, NEW_FREEZE, manifest)
    with ledger.connection(readonly=True) as db:
        before = b.legacy_snapshot(db)
    ledger.register(manifest, legacy_before=before)
    return ledger, manifest, before


def settled(ledger, sid, amount=3):
    lease = ledger.reserve(sid)
    ledger.mark_sent(lease["request_id"])
    assert ledger.settle(
        lease["request_id"],
        usage=dict(prompt_tokens=amount, completion_tokens=0, total_tokens=amount),
        http_success=True,
        response_model=p.MODEL,
        outcome="public_response_received",
    )
    return lease


def test_prospective_caps_exact_prefix_offset_and_old_closed_history(wallet):
    ledger, manifest, before = wallet
    assert (b.TOKEN_CAP, b.REQUEST_CAP, b.COMMON_CAP) == (109024251, 8300, 1000000000)
    assert ledger.freeze_id == OLD_FREEZE and ledger.completion_freeze_id == NEW_FREEZE
    sid = manifest["slots"][0]["registered_session"]["session_id"]
    lease = settled(ledger, sid)
    assert lease["attempt"] == 5 and lease["completion_freeze_id"] == NEW_FREEZE
    assert len(ledger.parent_requests(sid)) == 4
    assert len(ledger.new_requests(sid)) == len(ledger.requests(sid)) == 1
    assert [r["attempt"] for r in ledger.combined_requests(sid)] == [1, 2, 3, 4, 5]
    assert ledger.snapshot()["common_conservative_debit"] == 1000 + 5 * 115712 + 404 * 3 + 3
    with ledger.connection(readonly=True) as db:
        assert b.legacy_snapshot(db, before) == before
        assert db.execute("SELECT value FROM metadata WHERE key=?", (parent.FATAL,)).fetchone()[0]
    reopened = b.CompletionLedger(ledger.path, NEW_FREEZE, readonly=True)
    assert (
        reopened.manifest == manifest
        and reopened.registered(sid) == manifest["slots"][0]["registered_session"]
    )
    with pytest.raises(b.BudgetStop, match="readonly"):
        reopened.reserve(sid)
    with pytest.raises(b.BudgetStop, match="unfinished_slot"):
        ledger.reserve("original_slot_9000")


def test_old_tables_metadata_and_prefixes_cannot_be_mutated(wallet):
    ledger, _, _ = wallet
    statements = [
        "UPDATE kernel_recovery_requests SET charged_tokens=0",
        "DELETE FROM kernel_recovery_requests",
        "INSERT INTO kernel_recovery_requests(request_id) VALUES('new_old_request')",
        "UPDATE kernel_recovery_sessions SET state='registered'",
        "UPDATE prior_debits SET tokens=0",
        "DELETE FROM metadata WHERE key='kernel_recovery_fatal'",
        "INSERT OR REPLACE INTO metadata VALUES('kernel_recovery_fatal','cleared')",
        "UPDATE kernel_completion_sessions SET prefix_count=0",
    ]
    for sql in statements:
        with ledger.connection() as db, pytest.raises(sqlite3.IntegrityError):
            db.execute(sql)


def test_unknown_never_refunded_or_retried_and_new_stop_does_not_clear_old(wallet):
    ledger, _, _ = wallet
    sid = "original_slot_121"
    lease = ledger.reserve(sid)
    ledger.mark_sent(lease["request_id"])
    assert not ledger.settle(lease["request_id"], outcome="synthetic_network_unknown")
    assert ledger.new_requests(sid)[0]["charged_tokens"] == p.REQUEST_RESERVATION
    with pytest.raises(b.BudgetStop, match="no_retry"):
        ledger.reserve(sid)
    with pytest.raises(b.BudgetStop, match="cancel_only"):
        ledger.cancel_unsent(lease["request_id"], "cannot_prove_unsent")
    ledger.halt("synthetic_completion_stop")
    with pytest.raises(b.BudgetStop, match="purpose_not_open"):
        ledger.reserve("original_slot_122")
    with ledger.connection(readonly=True) as db:
        assert {
            r[0]
            for r in db.execute(
                "SELECT key FROM metadata WHERE key IN (?,?)", (parent.FATAL, b.FATAL)
            )
        } == {parent.FATAL, b.FATAL}


def test_four_parallel_known_settlements_and_finalization(wallet):
    ledger, _, before = wallet
    with ThreadPoolExecutor(max_workers=4) as pool:
        leases = list(pool.map(lambda i: settled(ledger, f"original_slot_{121 + i}"), range(4)))
    assert len({r["request_id"] for r in leases}) == 4
    for i in range(4):
        ledger.finish(f"original_slot_{121 + i}", "first_final")
    final = ledger.finalize(report_id="synthetic_completion_report")
    p.checked(final, "kernel_budget_finalization")
    assert final["completion_freeze_id"] == NEW_FREEZE and final["freeze_id"] == OLD_FREEZE
    assert final["purpose"] == b.PURPOSE and final["purpose_closed"] is True
    with pytest.raises(b.BudgetStop, match="purpose_not_open"):
        ledger.reserve("original_slot_130")
    with ledger.connection(readonly=True) as db:
        assert b.legacy_snapshot(db, before) == before
    stats = ledger.writer_statistics()
    assert stats["sqlite_lock_errors"] == 0 and stats["maximum_active_write_connections"] == 1


def test_failed_parent_prefix_is_not_admitted(tmp_path):
    path = tmp_path / "unsafe_shadow.sqlite3"
    manifest = make_closed_wallet(path)
    with sqlite3.connect(path) as db:
        db.execute(
            "UPDATE kernel_recovery_requests SET state='usage_unknown' WHERE "
            "request_id='original_request_0_1'"
        )
    ledger = b.CompletionLedger(path, NEW_FREEZE, manifest)
    with pytest.raises(b.BudgetStop, match="safe_known_successful_prefix"):
        ledger.register(manifest)
    with ledger.connection(readonly=True) as db:
        assert not db.execute(
            "SELECT 1 FROM sqlite_master WHERE name='kernel_completion_requests'"
        ).fetchone()


def test_common_cap_still_counts_all_five_old_unknowns(tmp_path):
    path = tmp_path / "common_limit_shadow.sqlite3"
    manifest = make_closed_wallet(path)
    with sqlite3.connect(path) as db:
        db.execute(
            "UPDATE prior_debits SET tokens=?", (b.COMMON_CAP - 5 * 115712 - 404 * 3 - 115712 + 1,)
        )
    ledger = b.CompletionLedger(path, NEW_FREEZE, manifest)
    ledger.register(manifest)
    with pytest.raises(b.BudgetStop, match="common_seven_purpose_cap"):
        ledger.reserve("original_slot_121")
    assert ledger.snapshot()["completion_conservative_debit"] == 0
