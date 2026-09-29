"""Authorized funding overlay on temporary SQLite only; no real wallet/API/GPU."""

import json
import sqlite3
from concurrent.futures import ThreadPoolExecutor

import pytest
from test_finance_unknown_abandonment import table
from test_finance_v6_probe_budget import reserve, settle
from test_finance_v10_budget import (  # noqa: F401
    BATCH_ID,
    SLOTS,
    args,
    connection_unknown,
    register,
    stopped_history,
    synthetic_parent,
    wallet,
)

from trusted_synthesis.finance_research import v10_funding as funding
from trusted_synthesis.finance_research.contracts import digest
from trusted_synthesis.finance_research.probe_budget import BudgetAmendmentError, BudgetUnavailable
from trusted_synthesis.finance_research.v10_budget import (
    acknowledge_connection_unknowns,
    review_episode_id,
)


def authorization(**changes):
    body = dict(
        schema="v10_funding_authorization.v1",
        user_reply=funding.USER_REPLY,
        batch_id=BATCH_ID,
        effective_hard_cap_microcny=2_000_000_000,
        effective_review_mapping_microcny=1_300_000_000,
    )
    body.update(changes)
    return {**body, "id": digest(body)}


def apply(ledger, backup, **changes):
    kwargs = dict(
        expected_run_id=ledger.run_id,
        expected_config_sha256=digest(ledger.config),
        batch_id=BATCH_ID,
        authorization=authorization(),
        backup_path=backup,
    )
    kwargs.update(changes)
    return funding.apply_v10_funding(ledger.path, **kwargs)


def test_append_only_backup_stream_and_idempotence_preserve_all_original_bytes(wallet, tmp_path):  # noqa: F811
    register(wallet)
    names = (
        "requests",
        "counters",
        "metadata",
        "events",
        "v10_quotas",
        "v10_request_allocations",
        "v8_request_quotas",
    )
    before = {name: table(wallet.path, name) for name in names}
    original = wallet.snapshot()
    backup = tmp_path / "pre-funding.sqlite3"
    record = apply(wallet, backup)
    assert record["applied_after_requests"] == 40076
    assert record["original_requests"]["rows"] == 40076
    assert record["backup"]["sha256"] == funding._file_sha(backup)
    assert all(table(backup, name) == rows for name, rows in before.items())
    assert all(
        table(wallet.path, name) == rows
        for name, rows in before.items()
        if name not in {"metadata", "events"}
    )
    assert dict(table(wallet.path, "metadata")) == {
        **dict(before["metadata"]),
        funding.KEY: json.dumps(
            record, ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False
        ),
    }
    assert table(wallet.path, "events")[:-1] == before["events"]
    current = wallet.snapshot()
    assert current["hard_cap_microcny"] == 800_000_000
    assert current["monetary_amendment"] == original["monetary_amendment"]
    assert current["previous_effective_hard_cap_microcny"] == 1_200_000_000
    assert current["effective_hard_cap_microcny"] == 2_000_000_000
    assert current["warning_microcny"] == 700_000_000 and current["request_cap"] == 258000
    part = current["v10_partition"]
    assert part["limits"]["review_mapping"]["microcny"] == 550_000_000
    assert part["effective_limits"]["review_mapping"]["microcny"] == 1_300_000_000
    assert part["effective_limits"]["generation"]["microcny"] == 100_000_000
    assert part["unallocated_microcny"] == 118_901_111 and not part["unallocated_spendable"]
    assert current["held_microcny"] == original["held_microcny"] == 144_834_560
    assert current["acknowledged_unknown_requests"] == 65
    sid = review_episode_id(BATCH_ID, SLOTS[0]["slot_id"], "A")
    iid, _ = reserve(wallet, sid, 2048)
    settle(wallet, iid, 20)
    after = {name: table(wallet.path, name) for name in names}
    assert apply(wallet, backup) == record
    assert all(table(wallet.path, name) == rows for name, rows in after.items())
    assert wallet.request_record(iid)["state"] == "SETTLED"
    with pytest.raises(BudgetUnavailable, match="no new generation"):
        reserve(wallet, SLOTS[1]["slot_id"], 2048)


@pytest.mark.parametrize("fault", ["pending", "unknown", "unrelated_halt", "wrong_authority"])
def test_nonquiescent_or_unapproved_funding_never_mutates_or_clears_halt(wallet, tmp_path, fault):  # noqa: F811
    register(wallet)
    changes = {}
    if fault in {"pending", "unknown"}:
        iid, _ = reserve(wallet, review_episode_id(BATCH_ID, SLOTS[0]["slot_id"], "A"), 2048)
        if fault == "unknown":
            wallet.mark_dispatched(iid)
            wallet.unknown(iid, reason="still unresolved original response")
    elif fault == "unrelated_halt":
        wallet.halt(reason="source mismatch must remain stopped", invocation_id="other")
    else:
        changes["authorization"] = authorization(effective_hard_cap_microcny=2_500_000_000)
    before = {n: table(wallet.path, n) for n in ("requests", "counters", "metadata", "events")}
    backup = tmp_path / "must-not-create.sqlite3"
    with pytest.raises(BudgetAmendmentError):
        apply(wallet, backup, **changes)
    assert not backup.exists()
    assert all(table(wallet.path, n) == rows for n, rows in before.items())


def test_failed_append_rolls_back_overlay_and_retains_recoverable_backup(
    wallet,  # noqa: F811
    tmp_path,
    monkeypatch,
):
    register(wallet)
    before = {
        n: table(wallet.path, n)
        for n in ("requests", "counters", "metadata", "events", "v10_quotas")
    }
    backup = tmp_path / "retained-failed-apply.sqlite3"

    def fail(db, record):
        db.execute("INSERT INTO metadata VALUES (?,?)", (funding.KEY, json.dumps(record)))
        raise RuntimeError("synthetic event publication failure")

    monkeypatch.setattr(funding, "_append", fail)
    with pytest.raises(RuntimeError, match="synthetic"):
        apply(wallet, backup)
    assert backup.is_file() and all(table(backup, n) == rows for n, rows in before.items())
    assert all(table(wallet.path, n) == rows for n, rows in before.items())
    assert wallet.snapshot()["effective_hard_cap_microcny"] == 1_200_000_000


def test_concurrent_effective_1300_guard_keeps_original_550_row_and_request_caps(wallet, tmp_path):  # noqa: F811
    register(wallet)
    apply(wallet, tmp_path / "before-concurrency.sqlite3")
    # Explicit counter-only synthetic edge, not a purported paid historical result.
    with sqlite3.connect(wallet.path) as db:
        db.execute("UPDATE v10_quotas SET spent=1296000000 WHERE category='review_mapping'")
        db.execute("UPDATE counters SET spent=spent+1296000000")

    def one(index):
        try:
            return reserve(wallet, review_episode_id(BATCH_ID, SLOTS[index]["slot_id"], "A"), 2048)
        except BudgetUnavailable:
            return None

    with ThreadPoolExecutor(max_workers=8) as workers:
        results = list(workers.map(one, range(8)))
    assert sum(item is not None for item in results) == 1
    snapshot = wallet.snapshot()
    consumed = snapshot["v10_partition"]["consumed"]["review_mapping"]
    assert consumed["spent"] > 550_000_000 and consumed["spent"] + consumed["held"] <= 1_300_000_000
    assert snapshot["exposure_microcny"] <= 2_000_000_000
    with sqlite3.connect(wallet.path) as db:
        assert db.execute(
            "SELECT money_cap,request_cap FROM v10_quotas WHERE category='review_mapping'"
        ).fetchone() == (550_000_000, 17000)
    assert snapshot["v10_partition"]["limits"]["generation"]["requests"] == 199000
    assert snapshot["v10_partition"]["unallocated_requests"] == 1924
    assert not snapshot["v10_partition"]["original_950_buffer_spendable"]


def test_existing_network_unknown_policy_preserves_new_hold_after_funding(wallet, tmp_path):  # noqa: F811
    register(wallet)
    apply(wallet, tmp_path / "before-unknown.sqlite3")
    episode = review_episode_id(BATCH_ID, SLOTS[0]["slot_id"], "A")
    expected = connection_unknown(wallet, args(wallet, episode=episode, output=4096))
    before = wallet.snapshot()
    receipt = acknowledge_connection_unknowns(wallet, batch_id=BATCH_ID, expected_requests=expected)
    after = wallet.snapshot()
    assert after["held_microcny"] == before["held_microcny"] == 144_834_560 + 2_129_920
    assert after["unknown_requests"] == after["acknowledged_unknown_requests"] == 66
    assert after["effective_hard_cap_microcny"] == 2_000_000_000
    assert receipt["records"][0]["model_response"] is None
    assert not receipt["records"][0]["material_eligible"] and not after["halt"]
