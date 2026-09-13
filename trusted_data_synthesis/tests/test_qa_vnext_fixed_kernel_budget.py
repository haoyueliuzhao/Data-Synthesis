"""Synthetic sixth-purpose recovery controls; never a live wallet or API request."""

import json
import shutil
import sqlite3
from concurrent.futures import ThreadPoolExecutor

import pytest
from test_qa_vnext_fixed_kernel_distribution import catalog

from trusted_synthesis.experiments.finance_qa_vnext_fixed_kernel_value import budget
from trusted_synthesis.experiments.finance_qa_vnext_fixed_kernel_value import population as pop
from trusted_synthesis.experiments.finance_qa_vnext_fixed_kernel_value import protocol as p

FREEZE = "synthetic_sixth_purpose_recovery_freeze"


@pytest.fixture(scope="module")
def population():
    return pop.make_population(catalog())


@pytest.fixture(scope="module")
def registry(population):
    return pop.make_registry(population, FREEZE, p.ORDER_SEED)


@pytest.fixture(scope="module")
def original_wallet(tmp_path_factory):
    path = tmp_path_factory.mktemp("synthetic_legacy_wallet") / "original.sqlite3"
    with sqlite3.connect(path) as db:
        db.execute("CREATE TABLE metadata(key TEXT PRIMARY KEY,value TEXT NOT NULL)")
        rows = [
            (
                "policy",
                json.dumps({"stage_id": p.OWNER, "common_new_experiment_cap": p.COMMON_CAP}),
            ),
            ("old_marker", "immutable_original_value"),
            ("probe01_finalization", json.dumps({"purpose_closed": True})),
            ("kernel_registration", "original_failed_purpose_registration_retained"),
            ("kernel_fatal", "original_database_locked_stop_retained"),
            ("kernel_finalization", json.dumps({"purpose_closed": True})),
            (
                "eval_surface_rewrite_finalization",
                json.dumps({"remaining_evaluation_attempts_permanently_closed": True}),
            ),
        ]
        db.executemany("INSERT INTO metadata VALUES(?,?)", rows)
        db.execute("CREATE TABLE prior_debits(name TEXT PRIMARY KEY,tokens INTEGER NOT NULL)")
        db.execute("INSERT INTO prior_debits VALUES('old_prior',221538)")
        for table in budget.OLD_RESERVATIONS:
            db.execute(f"""CREATE TABLE {table}(
                request_id TEXT PRIMARY KEY,state TEXT NOT NULL,reserved_tokens INTEGER NOT NULL,
                charged_tokens INTEGER NOT NULL,attempt INTEGER,created_at TEXT,
                prompt_tokens INTEGER,
                completion_tokens INTEGER,http_success INTEGER,response_model TEXT,outcome TEXT)""")
            db.execute(
                f"INSERT INTO {table}(request_id,state,reserved_tokens,charged_tokens) "
                "VALUES(?,'usage_unknown',115712,115712)",
                ("old_unknown_" + table,),
            )
        for table, count in (
            ("collection_sessions", 24640),
            ("probe01_sessions", 144),
            ("kernel_sessions", 10240),
        ):
            db.execute(f"CREATE TABLE {table}(session_id TEXT PRIMARY KEY,state TEXT NOT NULL)")
            db.executemany(
                f"INSERT INTO {table} VALUES(?,'finished')", [(str(i),) for i in range(count)]
            )
    return path


def create_wallet(tmp_path, original_wallet, registry, population, *, prior=None, register=True):
    path = tmp_path / "shadow.sqlite3"
    shutil.copyfile(original_wallet, path)
    if prior is not None:
        with sqlite3.connect(path) as db:
            db.execute("UPDATE prior_debits SET tokens=?", (prior,))
    ledger = budget.KernelLedger(path, FREEZE)
    with ledger.connection(readonly=True) as db:
        before = budget.legacy_snapshot(db)
    if register:
        ledger.register(registry, population, legacy_before=before)
    return ledger, before


@pytest.fixture
def wallet(tmp_path, original_wallet, registry, population):
    return create_wallet(tmp_path, original_wallet, registry, population)


def settle_ok(ledger, session_id, amount=3):
    lease = ledger.reserve(session_id)
    ledger.mark_sent(lease["request_id"])
    ledger.settle(
        lease["request_id"],
        usage={"prompt_tokens": amount, "completion_tokens": 0, "total_tokens": amount},
        http_success=True,
        response_model=p.MODEL,
        outcome="public_response_received",
    )
    return lease


def first_session(registry, n=0):
    return registry["sessions"][n]["session_id"]


def test_new_registered_bounds_are_not_old_probe_bounds():
    assert p.SESSION_CAP == 10240 and p.REQUEST_CAP == 327338
    assert p.TOKEN_CAP == 248730297 and p.COMMON_CAP == 1000000000
    assert p.REQUEST_RESERVATION == p.INPUT_ALLOWANCE + p.OUTPUT_ALLOWANCE == 115712
    assert budget.OLD_RESERVATIONS == (
        "reservations",
        "teacher_reservations",
        "eval_reservations",
        "probe01_requests",
        "kernel_requests",
    )


def test_migration_preserves_all_old_rows_schema_and_metadata(wallet, registry):
    ledger, before = wallet
    with ledger.connection(readonly=True) as db:
        assert budget.legacy_snapshot(db, before) == before
    rows = ledger.sessions()
    assert len(rows) == 10240
    assert {row["pool"] for row in rows} == {"A", "B"}
    assert {row["role"] for row in rows} == {"train", "sealed"}
    assert [json.loads(row["registered_json"]) for row in rows] == registry["sessions"]
    snapshot = ledger.snapshot()
    assert snapshot["kernel_conservative_debit"] == 0
    assert snapshot["common_conservative_debit"] == 221538 + 5 * 115712


def test_prior_not_double_counted_and_known_unused_lease_released(wallet, registry):
    ledger, before = wallet
    old = ledger.snapshot()["common_conservative_debit"]
    settle_ok(ledger, first_session(registry), 77)
    assert ledger.snapshot()["common_conservative_debit"] == old + 77
    assert ledger.snapshot()["kernel_conservative_debit"] == 77
    with ledger.connection(readonly=True) as db:
        assert budget.legacy_snapshot(db, before) == before


def test_registration_once_and_exact_frozen_identity(wallet, registry, population):
    ledger, before = wallet
    with pytest.raises(budget.BudgetStop):
        ledger.register(registry, population, legacy_before=before)
    with pytest.raises(budget.BudgetStop, match="frozen_purpose"):
        budget.KernelLedger(ledger.path, "different_freeze")


@pytest.mark.parametrize(
    "key", ["probe01_finalization", "eval_surface_rewrite_finalization", "kernel_finalization"]
)
def test_unclosed_old_purpose_rejected(tmp_path, original_wallet, registry, population, key):
    ledger, _ = create_wallet(tmp_path, original_wallet, registry, population, register=False)
    with ledger.connection() as db:
        db.execute("DELETE FROM metadata WHERE key=?", (key,))
        before = budget.legacy_snapshot(db)
    with pytest.raises(budget.BudgetStop, match="purpose_closed"):
        ledger.register(registry, population, legacy_before=before)


@pytest.mark.parametrize("table", ["collection_sessions", "probe01_sessions", "kernel_sessions"])
def test_unclosed_old_session_rejected(tmp_path, original_wallet, registry, population, table):
    ledger, _ = create_wallet(tmp_path, original_wallet, registry, population, register=False)
    with ledger.connection() as db:
        db.execute(f"UPDATE {table} SET state='running' WHERE session_id='0'")
        before = budget.legacy_snapshot(db)
    with pytest.raises(budget.BudgetStop, match="registered_collection_closed"):
        ledger.register(registry, population, legacy_before=before)


@pytest.mark.parametrize("table", budget.OLD_RESERVATIONS)
def test_old_inflight_never_reclaimed_for_registration(
    tmp_path, original_wallet, registry, population, table
):
    ledger, _ = create_wallet(tmp_path, original_wallet, registry, population, register=False)
    with ledger.connection() as db:
        db.execute(f"UPDATE {table} SET state='sent'")
        before = budget.legacy_snapshot(db)
    with pytest.raises(budget.BudgetStop, match="quiescent"):
        ledger.register(registry, population, legacy_before=before)


@pytest.mark.parametrize("table", budget.OLD_RESERVATIONS)
@pytest.mark.parametrize("attack", ["refund", "delete", "replace"])
def test_existing_old_unknowns_remain_immutable(wallet, table, attack):
    ledger, before = wallet
    with ledger.connection() as db, pytest.raises(sqlite3.IntegrityError):
        if attack == "refund":
            db.execute(f"UPDATE {table} SET charged_tokens=0")
        elif attack == "delete":
            db.execute(f"DELETE FROM {table}")
        else:
            db.execute(
                f"INSERT OR REPLACE INTO {table}(request_id,state,reserved_tokens,charged_tokens) "
                "VALUES(?,'settled',115712,0)",
                ("old_unknown_" + table,),
            )
    with ledger.connection(readonly=True) as db:
        assert budget.legacy_snapshot(db, before) == before


@pytest.mark.parametrize(
    "operation",
    [
        "INSERT INTO prior_debits VALUES('duplicate_prior',221538)",
        "UPDATE prior_debits SET tokens=0",
        "DELETE FROM prior_debits",
    ],
)
def test_prior_debits_cannot_be_replayed_or_refunded(wallet, operation):
    ledger, _ = wallet
    with ledger.connection() as db, pytest.raises(sqlite3.IntegrityError):
        db.execute(operation)


@pytest.mark.parametrize(
    "key",
    [
        "old_marker",
        "probe01_finalization",
        "eval_surface_rewrite_finalization",
        "kernel_registration",
        "kernel_fatal",
        "kernel_finalization",
        budget.PURPOSE,
    ],
)
@pytest.mark.parametrize("operation", ["update", "delete", "replace"])
def test_old_and_current_metadata_cannot_be_rewritten(wallet, key, operation):
    ledger, _ = wallet
    with ledger.connection() as db, pytest.raises(sqlite3.IntegrityError):
        if operation == "update":
            db.execute("UPDATE metadata SET value='tampered' WHERE key=?", (key,))
        elif operation == "delete":
            db.execute("DELETE FROM metadata WHERE key=?", (key,))
        else:
            db.execute("INSERT OR REPLACE INTO metadata VALUES(?,'tampered')", (key,))


@pytest.mark.parametrize(
    "field, value",
    [
        ("pool", "foreign"),
        ("role", "promoted"),
        ("basis", "invented"),
        ("registered_json", "{}"),
        ("ordinal", -1),
    ],
)
def test_registered_pool_role_identity_immutable(wallet, registry, field, value):
    ledger, _ = wallet
    with ledger.connection() as db, pytest.raises(sqlite3.IntegrityError):
        db.execute(
            f"UPDATE kernel_recovery_sessions SET {field}=? WHERE session_id=?",
            (value, first_session(registry)),
        )


@pytest.mark.parametrize("table", budget.OLD_RESERVATIONS)
def test_old_client_insert_path_sees_sixth_purpose_debit(
    tmp_path, original_wallet, registry, population, table
):
    prior = p.COMMON_CAP - 5 * 115712 - p.REQUEST_RESERVATION
    ledger, _ = create_wallet(tmp_path, original_wallet, registry, population, prior=prior)
    ledger.reserve(first_session(registry))
    with ledger.connection() as db, pytest.raises(sqlite3.IntegrityError, match="six_purpose_cap"):
        db.execute(
            f"INSERT INTO {table}(request_id,state,reserved_tokens,charged_tokens) "
            "VALUES('new_old_client','reserved',1,1)"
        )


def test_parallel_unique_sessions_respect_atomic_common_cap(
    tmp_path, original_wallet, registry, population
):
    prior = p.COMMON_CAP - 5 * 115712 - 3 * p.REQUEST_RESERVATION
    ledger, _ = create_wallet(tmp_path, original_wallet, registry, population, prior=prior)

    def reserve(i):
        try:
            return ledger.reserve(first_session(registry, i))
        except budget.BudgetStop:
            return None

    with ThreadPoolExecutor(max_workers=12) as pool:
        leases = list(pool.map(reserve, range(12)))
    assert sum(lease is not None for lease in leases) == 3
    assert ledger.snapshot()["common_conservative_debit"] == p.COMMON_CAP


def test_parallel_same_session_has_only_one_live_lease(wallet, registry):
    ledger, _ = wallet

    def reserve(_):
        try:
            return ledger.reserve(first_session(registry))
        except budget.BudgetStop:
            return None

    with ThreadPoolExecutor(max_workers=8) as pool:
        leases = list(pool.map(reserve, range(8)))
    assert sum(lease is not None for lease in leases) == 1


@pytest.mark.parametrize("cap", ["TOKEN_CAP", "REQUEST_CAP"])
def test_exact_purpose_cap_guards_no_refill(
    tmp_path, original_wallet, registry, population, monkeypatch, cap
):
    monkeypatch.setattr(p, cap, p.REQUEST_RESERVATION if cap == "TOKEN_CAP" else 1)
    ledger, _ = create_wallet(tmp_path, original_wallet, registry, population)
    settle_ok(ledger, first_session(registry), 7)
    with pytest.raises(budget.BudgetStop, match="subcap"):
        ledger.reserve(first_session(registry, 1))


def test_exact_maximum_32_responses_no_retry_or_33rd(wallet, registry):
    ledger, _ = wallet
    sid = first_session(registry)
    for _ in range(32):
        settle_ok(ledger, sid)
    with pytest.raises(budget.BudgetStop, match="no_retry"):
        ledger.reserve(sid)


@pytest.mark.parametrize(
    "usage",
    [
        None,
        {},
        {"prompt_tokens": True, "completion_tokens": 1, "total_tokens": 2},
        {"prompt_tokens": 1, "completion_tokens": 2, "total_tokens": 99},
    ],
)
def test_network_unknown_stays_charged_without_session_retry(wallet, registry, usage):
    ledger, _ = wallet
    sid = first_session(registry)
    lease = ledger.reserve(sid)
    ledger.mark_sent(lease["request_id"])
    assert not ledger.settle(lease["request_id"], usage=usage, outcome="network_unknown")
    assert ledger.requests(sid)[0]["charged_tokens"] == p.REQUEST_RESERVATION
    with pytest.raises(budget.BudgetStop, match="no_retry"):
        ledger.reserve(sid)
    assert ledger.reserve(first_session(registry, 1))


@pytest.mark.parametrize("kind", ["unknown", "wrong_model", "breach"])
def test_HTTP200_contract_failure_globally_halts_new_sends_but_settles_inflight(
    wallet, registry, kind
):
    ledger, _ = wallet
    leases = [ledger.reserve(first_session(registry, i)) for i in range(3)]
    for lease in leases[:2]:
        ledger.mark_sent(lease["request_id"])
    usage = (
        None
        if kind == "unknown"
        else {
            "prompt_tokens": p.INPUT_ALLOWANCE + 1 if kind == "breach" else 2,
            "completion_tokens": 1,
        }
    )
    if usage is not None:
        usage["total_tokens"] = usage["prompt_tokens"] + usage["completion_tokens"]
    ledger.settle(
        leases[0]["request_id"],
        usage=usage,
        http_success=True,
        response_model="wrong-model" if kind == "wrong_model" else p.MODEL,
        outcome=kind,
    )
    with pytest.raises((budget.BudgetStop, sqlite3.IntegrityError)):
        ledger.mark_sent(leases[2]["request_id"])
    with pytest.raises(budget.BudgetStop):
        ledger.reserve(first_session(registry, 3))
    ledger.settle(
        leases[1]["request_id"],
        usage={"prompt_tokens": 2, "completion_tokens": 1, "total_tokens": 3},
        http_success=True,
        response_model=p.MODEL,
        outcome="public_response_received",
    )
    assert ledger.requests(first_session(registry, 1))[0]["charged_tokens"] == 3
    assert "study_fatal" in ledger.snapshot()["persisted_stops"]


@pytest.mark.parametrize(
    "attack",
    ["fractional_tokens", "null_http", "null_outcome", "unknown_refund", "null_breach_total"],
)
def test_SQL_settlement_bypass_rejected(wallet, registry, attack):
    ledger, _ = wallet
    lease = ledger.reserve(first_session(registry))
    ledger.mark_sent(lease["request_id"])
    updates = {
        "fractional_tokens": (
            "state='settled',prompt_tokens=1.5,completion_tokens=0.5,"
            "reported_total_tokens=2,charged_tokens=2,http_success=1,"
            "outcome='public_response_received'"
        ),
        "null_http": (
            "state='settled',prompt_tokens=1,completion_tokens=1,reported_total_tokens=2,"
            "charged_tokens=2,http_success=NULL,outcome='public_response_received'"
        ),
        "null_outcome": (
            "state='settled',prompt_tokens=1,completion_tokens=1,reported_total_tokens=2,"
            "charged_tokens=2,http_success=1,outcome=NULL"
        ),
        "unknown_refund": "state='usage_unknown',charged_tokens=0,http_success=0,outcome='unknown'",
        "null_breach_total": (
            "state='budget_breach',prompt_tokens=100000,completion_tokens=1,"
            "reported_total_tokens=NULL,charged_tokens=100001,http_success=1,outcome='breach'"
        ),
    }
    with ledger.connection() as db, pytest.raises(sqlite3.IntegrityError):
        db.execute(
            "UPDATE kernel_recovery_requests SET " + updates[attack] + " WHERE request_id=?",
            (lease["request_id"],),
        )
    assert ledger.requests()[0]["state"] == "sent"
    assert ledger.requests()[0]["charged_tokens"] == p.REQUEST_RESERVATION


def test_request_replace_delete_double_send_settle_and_premature_finish_rejected(wallet, registry):
    ledger, _ = wallet
    sid = first_session(registry)
    lease = ledger.reserve(sid)
    with pytest.raises(sqlite3.IntegrityError, match="inflight"):
        ledger.finish(sid, "pretend_completed")
    with ledger.connection() as db:
        with pytest.raises(sqlite3.IntegrityError):
            db.execute("DELETE FROM kernel_recovery_requests")
        with pytest.raises(sqlite3.IntegrityError, match="replacement"):
            db.execute(
                "INSERT OR REPLACE INTO kernel_recovery_requests("
                "request_id,session_id,attempt,state,"
                "reserved_tokens,charged_tokens,created_at) VALUES(?,?,2,'reserved',?,?,?)",
                (lease["request_id"], sid, p.REQUEST_RESERVATION, p.REQUEST_RESERVATION, p.now()),
            )
    ledger.mark_sent(lease["request_id"])
    with pytest.raises(budget.BudgetStop):
        ledger.mark_sent(lease["request_id"])
    ledger.settle(lease["request_id"], outcome="unknown")
    with pytest.raises(budget.BudgetStop):
        ledger.settle(lease["request_id"], outcome="unknown")


def test_guards_must_be_present_for_every_application_send_and_settle(wallet, registry):
    ledger, _ = wallet
    lease = ledger.reserve(first_session(registry))
    with ledger.connection() as db:
        db.execute("DROP TRIGGER kernel_recovery_request_state")
    with pytest.raises(budget.BudgetStop, match="guards_present"):
        ledger.mark_sent(lease["request_id"])
    with pytest.raises(budget.BudgetStop, match="guards_present"):
        ledger.settle(lease["request_id"], outcome="unknown")


def test_halt_and_finalization_are_append_only_and_do_not_reopen_old_purposes(wallet, registry):
    ledger, before = wallet
    settle_ok(ledger, first_session(registry))
    ledger.finish(first_session(registry), "first_final")
    ledger.halt("synthetic_stop")
    ledger.halt("second_reason_does_not_overwrite")
    final = ledger.finalize(report_id="synthetic_shadow_report")
    assert final["purpose_closed"] and final["old_purposes_not_reopened"]
    with pytest.raises(budget.BudgetStop):
        ledger.reserve(first_session(registry, 1))
    with pytest.raises(budget.BudgetStop):
        ledger.finalize(report_id="second")
    with ledger.connection(readonly=True) as db:
        assert budget.legacy_snapshot(db, before) == before
        assert (
            db.execute("SELECT value FROM metadata WHERE key=?", (budget.FATAL,)).fetchone()[0]
            == "synthetic_stop"
        )


def test_new_unrelated_future_metadata_not_frozen_as_old_history(wallet):
    ledger, _ = wallet
    with ledger.connection() as db:
        db.execute("INSERT INTO metadata VALUES('future_unrelated_key','a')")
        db.execute("UPDATE metadata SET value='b' WHERE key='future_unrelated_key'")
        db.execute("DELETE FROM metadata WHERE key='future_unrelated_key'")


def test_shadow_control_is_explicit_simulation_and_never_mutates_source(
    tmp_path, original_wallet, registry, population
):
    before = p.sha(original_wallet)
    evidence = budget.run_shadow_control(
        original_wallet, tmp_path / "exclusive_shadow", registry, population, FREEZE
    )
    assert p.checked(evidence, "wallet_shadow_control") == evidence
    assert p.sha(original_wallet) == before
    assert evidence["source_legacy_snapshot_before"] == evidence["source_legacy_snapshot_after"]
    assert evidence["shadow_simulated_usage_tokens"] == 3
    assert evidence["live_API_calls"] == evidence["live_new_tokens"] == 0
    assert evidence["source_new_purpose_registered"] is False
    assert evidence["not_formal_material_or_training_evidence"] is True
    with pytest.raises(budget.BudgetStop, match="exclusive_shadow"):
        budget.run_shadow_control(
            original_wallet, tmp_path / "exclusive_shadow", registry, population, FREEZE
        )


@pytest.mark.parametrize(
    "field,value",
    [("reserved_tokens", 1), ("charged_tokens", 1), ("attempt", 0), ("state", "sent")],
)
def test_SQL_new_request_must_reserve_full_lease_before_send(wallet, registry, field, value):
    ledger, _ = wallet
    fields = dict(
        request_id="malformed_direct_sql",
        session_id=first_session(registry),
        attempt=1,
        state="reserved",
        reserved_tokens=p.REQUEST_RESERVATION,
        charged_tokens=p.REQUEST_RESERVATION,
        created_at=p.now(),
    )
    fields[field] = value
    with ledger.connection() as db, pytest.raises(sqlite3.IntegrityError):
        db.execute(
            "INSERT INTO kernel_recovery_requests("
            + ",".join(fields)
            + ") VALUES("
            + ",".join("?" for _ in fields)
            + ")",
            tuple(fields.values()),
        )
    assert ledger.snapshot()["kernel_conservative_debit"] == 0


def test_proven_unsent_cancellation_preserves_row_and_cannot_retry(wallet, registry):
    ledger, before = wallet
    sid = first_session(registry)
    lease = ledger.reserve(sid)
    cancellation = ledger.cancel_unsent(lease["request_id"], "request_persistence_failed")
    assert cancellation["actual_HTTP_requests"] == 0
    assert cancellation["released_unused_allowance"] == p.REQUEST_RESERVATION
    row = ledger.requests(sid)[0]
    assert row["state"] == "not_sent" and row["reserved_tokens"] == p.REQUEST_RESERVATION
    assert row["charged_tokens"] == row["prompt_tokens"] == row["completion_tokens"] == 0
    assert row["reported_total_tokens"] == row["http_success"] == 0
    assert row["response_model"] is None
    assert row["outcome"] == "not_sent:request_persistence_failed"
    with pytest.raises(budget.BudgetStop):
        ledger.cancel_unsent(lease["request_id"], "double_cancel")
    with pytest.raises(budget.BudgetStop):
        ledger.reserve(sid)
    with pytest.raises(budget.BudgetStop):
        ledger.mark_sent(lease["request_id"])
    ledger.finish(sid, "unsent_cancelled")
    ledger.finalize(report_id="synthetic_unsent_control")
    with ledger.connection(readonly=True) as db:
        assert budget.legacy_snapshot(db, before) == before


@pytest.mark.parametrize("state", ["sent", "usage_unknown", "settled"])
def test_sent_or_unknown_rows_can_never_be_cancelled_as_unsent(wallet, registry, state):
    ledger, _ = wallet
    lease = ledger.reserve(first_session(registry))
    ledger.mark_sent(lease["request_id"])
    if state == "usage_unknown":
        ledger.settle(lease["request_id"], outcome="network_unknown")
    elif state == "settled":
        ledger.settle(
            lease["request_id"],
            usage={"prompt_tokens": 1, "completion_tokens": 0, "total_tokens": 1},
            http_success=True,
            response_model=p.MODEL,
            outcome="public_response_received",
        )
    before = ledger.requests()
    with pytest.raises(budget.BudgetStop, match="only_proven_unsent"):
        ledger.cancel_unsent(lease["request_id"], "false_claim")
    with ledger.connection() as db, pytest.raises(sqlite3.IntegrityError):
        db.execute(
            """UPDATE kernel_recovery_requests SET state='not_sent',charged_tokens=0,
            prompt_tokens=0,completion_tokens=0,reported_total_tokens=0,http_success=0,
            response_model=NULL,outcome='not_sent:forged' WHERE request_id=?""",
            (lease["request_id"],),
        )
    assert ledger.requests() == before


@pytest.mark.parametrize(
    "field, value",
    [
        ("charged_tokens", 1),
        ("prompt_tokens", None),
        ("http_success", 1),
        ("response_model", p.MODEL),
        ("outcome", "network_unknown"),
    ],
)
def test_SQL_unsent_cancellation_must_prove_zero_send_contract(wallet, registry, field, value):
    ledger, _ = wallet
    lease = ledger.reserve(first_session(registry))
    changes = dict(
        state="not_sent",
        charged_tokens=0,
        prompt_tokens=0,
        completion_tokens=0,
        reported_total_tokens=0,
        http_success=0,
        response_model=None,
        outcome="not_sent:x",
    )
    changes[field] = value
    with ledger.connection() as db, pytest.raises(sqlite3.IntegrityError):
        db.execute(
            "UPDATE kernel_recovery_requests SET "
            + ",".join(key + "=?" for key in changes)
            + " WHERE request_id=?",
            (*changes.values(), lease["request_id"]),
        )
    assert ledger.requests()[0]["state"] == "reserved"


def test_128_parallel_stop_cancels_only_unsent_and_closes_conservatively(wallet, registry):
    ledger, before = wallet

    def reserve(index):
        return ledger.reserve(first_session(registry, index))

    with ThreadPoolExecutor(max_workers=16) as pool:
        leases = list(pool.map(reserve, range(128)))
    for lease in leases[:32]:
        ledger.mark_sent(lease["request_id"])
    ledger.halt("synthetic_parallel_global_stop")
    with pytest.raises(sqlite3.IntegrityError):
        ledger.mark_sent(leases[32]["request_id"])
    with ThreadPoolExecutor(max_workers=16) as pool:
        cancellations = list(
            pool.map(
                lambda lease: ledger.cancel_unsent(lease["request_id"], "stopped_before_HTTP"),
                leases[32:],
            )
        )
    assert len(cancellations) == 96
    for lease in leases[:32]:
        ledger.settle(lease["request_id"], outcome="synthetic_network_unknown")
    for lease in leases:
        ledger.finish(lease["session_id"], "synthetic_stopped")
    ledger.finalize(report_id="synthetic_parallel_stop_only")
    snapshot = ledger.snapshot()
    assert snapshot["kernel_conservative_debit"] == 32 * p.REQUEST_RESERVATION
    assert {row["state"]: row["requests"] for row in snapshot["request_states"]} == {
        "not_sent": 96,
        "usage_unknown": 32,
    }
    with ledger.connection(readonly=True) as db:
        assert budget.legacy_snapshot(db, before) == before
