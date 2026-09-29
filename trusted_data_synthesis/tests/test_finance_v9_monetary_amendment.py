"""Authorized cap overlay on synthetic SQLite only; no real wallet or API."""

import json
import sqlite3
from concurrent.futures import ThreadPoolExecutor

import pytest
from test_finance_unknown_abandonment import table
from test_finance_v6_probe_budget import reserve
from test_finance_v8_request_partition import IDS, historical_wallet, partition

from trusted_synthesis.finance_research.contracts import digest, invocation_identity
from trusted_synthesis.finance_research.probe_budget import (
    V9_MONETARY_AMENDMENT_ACTION,
    V9_MONETARY_AMENDMENT_KEY,
    BudgetAmendmentError,
    BudgetUnavailable,
    ProbeBudget,
    apply_v9_monetary_amendment,
    read_budget_snapshot,
)


@pytest.fixture(scope="module")
def synthetic_parent(tmp_path_factory):
    directory = tmp_path_factory.mktemp("v9-synthetic-parent")
    ledger, unknown_id, held = historical_wallet(directory)
    partition(ledger)
    # Explicit CPU fixture copies, not actual API calls or production evidence.
    with sqlite3.connect(ledger.path) as db:
        db.row_factory = sqlite3.Row
        old = dict(db.execute("SELECT * FROM requests WHERE state='SETTLED' LIMIT 1").fetchone())
        usage = json.loads(old["usage_json"])
        columns, rows, allocations = list(old), [], []
        for index in range(16394):
            generation = index < 16286
            episode = IDS[index % 8000] if generation else f"v8review:synthetic-{index}"
            coords = invocation_identity(
                dict(run_id=ledger.run_id, episode_id=episode, attempt_index=1),
                turn_index=index // 8000 if generation else 0,
            )
            row = {
                **old,
                "invocation_id": coords["invocation_id"],
                "coordinates_json": json.dumps(coords),
            }
            rows.append(tuple(row[k] for k in columns))
            allocations.append(
                (
                    coords["invocation_id"],
                    "generation" if generation else "technical_review",
                    episode,
                )
            )
        db.executemany(
            f"INSERT INTO requests ({','.join(columns)}) VALUES ({','.join('?' for _ in columns)})",
            rows,
        )
        db.executemany("INSERT INTO v8_request_allocations VALUES (?,?,?)", allocations)
        db.execute("UPDATE v8_request_quotas SET consumed=16286 WHERE category='generation'")
        db.execute("UPDATE v8_request_quotas SET consumed=108 WHERE category='technical_review'")
        db.execute(
            "UPDATE counters SET requests=requests+16394, dispatched=dispatched+16394, "
            "spent=spent+?,prompt_tokens=prompt_tokens+?,hit_tokens=hit_tokens+?,"
            "miss_tokens=miss_tokens+?,completion_tokens=completion_tokens+?",
            tuple(
                16394 * value
                for value in (
                    old["settled_microcny"],
                    usage["prompt_tokens"],
                    usage["prompt_cache_hit_tokens"],
                    usage["prompt_cache_miss_tokens"],
                    usage["completion_tokens"],
                )
            ),
        )
    assert ledger.snapshot()["requests_reserved"] == 35336
    return ledger.path, ledger.config, unknown_id, held


@pytest.fixture
def wallet(tmp_path, synthetic_parent):
    original, config, iid, held = synthetic_parent
    path = tmp_path / "temporary-v9.sqlite3"
    with sqlite3.connect(original) as source, sqlite3.connect(path) as target:
        source.backup(target)
    ledger = ProbeBudget(
        path,
        run_id=config["run_id"],
        price_sheet=config["price_sheet"],
        max_output_tokens=config["max_output_tokens"],
        purpose=config["purpose"],
        request_cap=config["request_cap"],
    )
    return ledger, iid, held


def authorization(ledger, **changes):
    body = dict(
        schema="v9_production_funding_decision.v1",
        explicit_user_authorization=True,
        user_reply="批准1200元总上限及上述风险",
        hard_cap_microcny=1200000000,
        budget_config_sha256=digest(ledger.config),
        preflight_id="ceeb89519387dfd98e47015128137b9fe901689644c9b4f42391782f399ce4bc",
        no_prefix_training=True,
        risk_of_incomplete_cohort_accepted=True,
        strategy="bounded_full_cohort_attempt",
    )
    body.update(changes)
    return {**body, "id": digest(body)}


def apply(ledger, **changes):
    args = dict(
        expected_run_id=ledger.run_id,
        expected_config_sha256=digest(ledger.config),
        amendment_id="v9-explicit-1200-fixture",
        effective_hard_cap_microcny=1200000000,
        authorization=authorization(ledger),
    )
    args.update(changes)
    return apply_v9_monetary_amendment(ledger.path, **args)


def test_overlay_preserves_original_bytes_rows_holds_and_is_idempotent(wallet):
    ledger, iid, held = wallet
    before = {
        name: table(ledger.path, name)
        for name in (
            "requests",
            "counters",
            "metadata",
            "events",
            "v8_request_quotas",
            "v8_request_allocations",
        )
    }
    old = read_budget_snapshot(ledger.path)
    record = apply(ledger)
    new = read_budget_snapshot(ledger.path)
    assert new["config"] == old["config"] == ledger.config
    assert new["config_sha256"] == old["config_sha256"]
    assert new["acknowledged_unknowns"] == old["acknowledged_unknowns"]
    assert new["snapshot"]["hard_cap_microcny"] == ledger.hard_cap_microcny == 800000000
    assert new["snapshot"]["effective_hard_cap_microcny"] == 1200000000
    assert (
        new["snapshot"]["remaining_exposure_microcny"]
        == old["snapshot"]["remaining_exposure_microcny"] + 400000000
    )
    assert new["snapshot"]["warning_microcny"] == 700000000
    assert new["snapshot"]["request_cap"] == 258000
    assert new["snapshot"]["request_partition"] == old["snapshot"]["request_partition"]
    assert new["snapshot"]["held_microcny"] == held == 2228224
    assert ledger.request_record(iid)["state"] == "UNKNOWN"
    assert ledger.request_record(iid)["usage_json"] is None
    for name in ("requests", "counters", "v8_request_quotas", "v8_request_allocations"):
        assert table(ledger.path, name) == before[name]
    assert table(ledger.path, "events")[:-1] == before["events"]
    assert table(ledger.path, "events")[-1][2] == V9_MONETARY_AMENDMENT_ACTION
    assert dict(table(ledger.path, "metadata")) == {
        **dict(before["metadata"]),
        V9_MONETARY_AMENDMENT_KEY: json.dumps(
            record, ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False
        ),
    }
    after = {name: table(ledger.path, name) for name in before}
    assert apply(ledger) == record
    assert all(table(ledger.path, name) == rows for name, rows in after.items())
    with pytest.raises(BudgetAmendmentError, match="cannot be replaced"):
        apply(ledger, amendment_id="different-authorization")


def test_old_live_instance_observes_effective_cap_atomically_and_never_exceeds_1200(wallet):
    ledger, _, held = wallet
    record = apply(ledger)
    original_exposure = ledger.snapshot()["exposure_microcny"]
    reservation = ledger.price_sheet.cost_microcny(hit=0, miss=1048576, output=16384)
    expected = (1200000000 - original_exposure) // reservation

    def one(index):
        try:
            reserve(ledger, f"v8prod:reserve-{index}", 16384)
            return True
        except BudgetUnavailable:
            return False

    with ThreadPoolExecutor(max_workers=8) as pool:
        results = list(pool.map(one, range(expected + 16)))
    assert sum(results) == expected
    state = ledger.snapshot()
    assert 800000000 < state["exposure_microcny"] <= 1200000000
    assert state["held_microcny"] == held + expected * reservation
    assert state["exposure_warning_reached"] is True
    assert state["warning_reached"] is False
    assert state["request_partition"]["consumed"]["production_review"] == expected
    assert state["halt"] is None
    assert apply(ledger) == record  # Same authorization is lookup, even with active pending calls.
    reopened = ProbeBudget(
        ledger.path,
        run_id=ledger.run_id,
        price_sheet=ledger.price_sheet,
        max_output_tokens=16384,
        purpose=ledger.purpose,
        request_cap=258000,
    )
    assert reopened.config == ledger.config
    assert reopened.snapshot() == state


@pytest.mark.parametrize(
    "failure", ["pending", "unknown", "halt", "production_started", "counters"]
)
def test_preproduction_registration_rejects_unsafe_state_without_mutation(wallet, failure):
    ledger, _, _ = wallet
    if failure in {"pending", "unknown", "production_started"}:
        iid, _ = reserve(ledger, "v8prod:premature", 16384)
        if failure == "unknown":
            ledger.mark_dispatched(iid)
            ledger.unknown(iid, reason="synthetic transport unknown")
        elif failure == "production_started":
            from test_finance_v6_probe_budget import settle

            settle(ledger, iid, 20)
    elif failure == "halt":
        ledger.halt(reason="separate pause", invocation_id="separate")
    else:
        with sqlite3.connect(ledger.path) as db:
            db.execute("UPDATE counters SET spent=spent+1")
    before = {
        name: table(ledger.path, name) for name in ("requests", "counters", "metadata", "events")
    }
    with pytest.raises(BudgetAmendmentError):
        apply(ledger)
    assert all(table(ledger.path, name) == rows for name, rows in before.items())


@pytest.mark.parametrize("failure", ["unapproved", "risk", "old_config", "cap", "new_preflight"])
def test_bound_user_authority_cannot_be_inferred_or_expanded(wallet, failure):
    ledger, _, _ = wallet
    changes = {
        "unapproved": dict(authorization=authorization(ledger, explicit_user_authorization=False)),
        "risk": dict(authorization=authorization(ledger, risk_of_incomplete_cohort_accepted=False)),
        "old_config": dict(expected_config_sha256="0" * 64),
        "cap": dict(effective_hard_cap_microcny=1600000000),
        "new_preflight": dict(authorization=authorization(ledger, preflight_id="0" * 64)),
    }[failure]
    before = {name: table(ledger.path, name) for name in ("counters", "metadata", "events")}
    with pytest.raises(BudgetAmendmentError):
        apply(ledger, **changes)
    assert all(table(ledger.path, name) == rows for name, rows in before.items())


def test_overlay_tampering_and_missing_database_fail_closed(wallet, tmp_path):
    ledger, _, _ = wallet
    apply(ledger)
    with sqlite3.connect(ledger.path) as db:
        db.execute("DELETE FROM events WHERE action=?", (V9_MONETARY_AMENDMENT_ACTION,))
    with pytest.raises(BudgetAmendmentError, match="authorization/config changed"):
        ledger.snapshot()
    with pytest.raises(BudgetAmendmentError, match="authorization/config changed"):
        reserve(ledger, "v8prod:tampered", 16384)
    missing = tmp_path / "no-ledger.sqlite3"
    with pytest.raises(BudgetAmendmentError, match="missing"):
        apply_v9_monetary_amendment(
            missing,
            expected_run_id=ledger.run_id,
            expected_config_sha256=digest(ledger.config),
            amendment_id="explicit",
            effective_hard_cap_microcny=1200000000,
            authorization=authorization(ledger),
        )
    assert not missing.exists()
