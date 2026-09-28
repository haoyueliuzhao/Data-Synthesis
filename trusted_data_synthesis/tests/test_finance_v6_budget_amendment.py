"""Only temporary SQLite ledgers; no production database, API, credentials or GPU."""

import copy
import json
import sqlite3
from concurrent.futures import ThreadPoolExecutor

import pytest
from test_finance_research_probe_budget import sheet, usage
from test_finance_v6_probe_budget import reserve, settle

from trusted_synthesis.finance_research.contracts import digest
from trusted_synthesis.finance_research.probe_budget import (
    PURPOSE,
    V6_PURPOSE,
    V6_REVIEW_AMENDMENT_ACTION,
    V6_REVIEW_AMENDMENT_PAUSE,
    BudgetAmendmentError,
    DuplicateInvocation,
    InvalidUsage,
    ProbeBudget,
    apply_v6_review_amendment,
)

CAPS = [2048, 16384, 32768, 65536, 131072]
AMENDMENT = "v6-review-capacity-control-01"


def open_budget(path, **changes):
    return ProbeBudget(
        **dict(
            path=path,
            run_id="same-original-v6-run",
            price_sheet=sheet(),
            max_output_tokens=16384,
            purpose=V6_PURPOSE,
            hard_cap_microcny=800_000_000,
            warning_microcny=700_000_000,
            request_cap=258000,
        )
        | changes
    )


def reopen(path, **changes):
    return open_budget(
        path,
        **dict(max_output_tokens=max(CAPS), amendment_id=AMENDMENT, allowed_output_limits=CAPS)
        | changes,
    )


def amendment(ledger, **changes):
    parameters = dict(
        expected_run_id=ledger.run_id,
        expected_config_sha256=digest(ledger.config),
        amendment_id=AMENDMENT,
        allowed_review_output_limits=CAPS,
        evidence=dict(user_authorization="CPU control only", retained_original_reviews=True),
    )
    parameters.update(changes)
    return apply_v6_review_amendment(ledger.path, **parameters)


def rows(path, table):
    with sqlite3.connect(path) as db:
        return db.execute(f"SELECT * FROM {table} ORDER BY 1").fetchall()


def paused_budget(path):
    ledger = open_budget(path)
    generation, _ = reserve(ledger, "old-generation", 2048)
    settle(ledger, generation, 20)
    review, _ = reserve(ledger, "old-review", 16384)
    settle(ledger, review, 16384)
    ledger.halt(
        reason=V6_REVIEW_AMENDMENT_PAUSE, invocation_id="user-audit", evidence={"authorized": True}
    )
    return ledger, (generation, review)


def test_amendment_preserves_every_paid_request_counter_fee_and_original_limit(tmp_path):
    ledger, identities = paused_budget(tmp_path / "original.sqlite3")
    before_requests, before_counters = rows(ledger.path, "requests"), rows(ledger.path, "counters")
    before_events, before = rows(ledger.path, "events"), ledger.snapshot()
    record = amendment(ledger)
    assert rows(ledger.path, "requests") == before_requests
    assert rows(ledger.path, "counters") == before_counters
    assert rows(ledger.path, "events")[:-1] == before_events
    assert rows(ledger.path, "events")[-1][2] == V6_REVIEW_AMENDMENT_ACTION
    assert record["old_config"] == ledger.config
    assert record["old_config_sha256"] == digest(ledger.config)
    assert record["new_config_sha256"] == digest(record["new_config"])
    assert record["preserved_counters"]["spent"] == before["settled_tariff_microcny"] > 0
    current = reopen(ledger.path)
    assert current.config == record["new_config"]
    after = current.snapshot()
    assert after | {"halt": before["halt"]} == before
    assert after["halt"] is None
    assert current.allowed_output_limits == tuple(CAPS)
    assert current.max_output_tokens == 131072
    assert current.config["hard_cap_microcny"] == 800_000_000
    assert current.config["warning_microcny"] == 700_000_000
    assert current.config["request_cap"] == 258000
    assert [
        json.loads(current.request_record(i)["request_body"])["max_tokens"] for i in identities
    ] == [2048, 16384]
    with sqlite3.connect(ledger.path) as db:
        stored = json.loads(
            db.execute(
                "SELECT value FROM metadata WHERE key=?", ("v6_review_amendment:" + AMENDMENT,)
            ).fetchone()[0]
        )
    assert stored == record


@pytest.mark.parametrize(
    "change",
    [
        dict(),
        dict(amendment_id=AMENDMENT),
        dict(allowed_output_limits=CAPS),
        dict(amendment_id="different", allowed_output_limits=CAPS, max_output_tokens=131072),
        dict(amendment_id=AMENDMENT, allowed_output_limits=CAPS[:-1], max_output_tokens=65536),
        dict(
            amendment_id=AMENDMENT,
            allowed_output_limits=CAPS,
            max_output_tokens=131072,
            hard_cap_microcny=900_000_000,
        ),
    ],
)
def test_old_implicit_or_changed_constructor_cannot_open_amended_budget(tmp_path, change):
    ledger, _ = paused_budget(tmp_path / "original.sqlite3")
    amendment(ledger)
    before = rows(ledger.path, "counters")
    with pytest.raises(ValueError):
        open_budget(ledger.path, **change)
    assert rows(ledger.path, "counters") == before


def test_old_live_object_cannot_reserve_or_halt_after_config_amendment(tmp_path):
    ledger, _ = paused_budget(tmp_path / "original.sqlite3")
    amendment(ledger)
    before = rows(ledger.path, "counters")
    with pytest.raises(ValueError, match="stale"):
        reserve(ledger, "old-worker-raced", 2048)
    with pytest.raises(ValueError, match="stale"):
        ledger.halt(reason="late old worker", invocation_id="old")
    assert rows(ledger.path, "counters") == before
    assert reopen(ledger.path).snapshot()["halt"] is None


def test_request_specific_limits_still_govern_new_and_old_requests(tmp_path):
    old, identities = paused_budget(tmp_path / "original.sqlite3")
    amendment(old)
    ledger = reopen(old.path)
    with pytest.raises(DuplicateInvocation):
        reserve(ledger, "old-review", 16384)
    identity, held = reserve(ledger, "new-large-review", 131072)
    assert held == sheet().cost_microcny(hit=0, miss=1048576, output=131072)
    assert settle(ledger, identity, 100000) == sheet().cost_microcny(hit=41, miss=59, output=100000)
    small, _ = reserve(ledger, "new-original-size-generation", 2048)
    ledger.mark_dispatched(small)
    before = ledger.snapshot()
    with pytest.raises(InvalidUsage, match="exceeds"):
        ledger.settle(
            small,
            usage=usage(output=2049),
            http_status=200,
            response_classification="model_response",
            response_body=b"{}",
        )
    assert ledger.snapshot() == before
    assert ledger.request_record(small)["state"] == "DISPATCHED"
    assert all(ledger.request_record(i)["state"] == "SETTLED" for i in identities)


@pytest.mark.parametrize(
    "change",
    [
        dict(expected_run_id="other-run"),
        dict(expected_config_sha256="0" * 64),
        dict(allowed_review_output_limits=[2048, 32768]),
        dict(allowed_review_output_limits=[2048, 16384]),
        dict(allowed_review_output_limits=[2048, 16384, 999999]),
        dict(allowed_review_output_limits=[2048, 16384, 32768, 32768]),
        dict(allowed_review_output_limits=[2048, 16384, True]),
        dict(evidence={}),
    ],
)
def test_wrong_identity_or_unapproved_capacity_does_not_clear_pause_or_modify_any_rows(
    tmp_path, change
):
    ledger, _ = paused_budget(tmp_path / "original.sqlite3")
    before = {
        name: rows(ledger.path, name) for name in ("metadata", "requests", "counters", "events")
    }
    with pytest.raises(ValueError):
        amendment(ledger, **change)
    assert {name: rows(ledger.path, name) for name in before} == before


@pytest.mark.parametrize("reason", [None, "unknown_service_cost", "budget_exhausted"])
def test_only_exact_user_authorized_pause_can_be_cleared(tmp_path, reason):
    ledger = open_budget(tmp_path / "original.sqlite3")
    if reason:
        ledger.halt(reason=reason, invocation_id="other-halt")
    before = rows(ledger.path, "metadata")
    with pytest.raises(BudgetAmendmentError, match="pause"):
        amendment(ledger)
    assert rows(ledger.path, "metadata") == before


def test_paid_inflight_service_failure_after_pause_cannot_be_hidden_by_first_halt(tmp_path):
    ledger = open_budget(tmp_path / "original.sqlite3")
    identity, _ = reserve(ledger, "inflight-at-user-pause", 16384)
    ledger.mark_dispatched(identity)
    ledger.halt(reason=V6_REVIEW_AMENDMENT_PAUSE, invocation_id="authorized")
    ledger.settle(
        identity,
        usage=usage(),
        http_status=503,
        response_classification="service_failure",
        response_body=b'{"error":"service"}',
    )
    assert ledger.snapshot()["halt"]["reason"] == V6_REVIEW_AMENDMENT_PAUSE
    assert not ledger.unsettled() and ledger.snapshot()["held_microcny"] == 0
    before = rows(ledger.path, "metadata"), rows(ledger.path, "counters")
    with pytest.raises(BudgetAmendmentError, match="another halt"):
        amendment(ledger)
    assert (rows(ledger.path, "metadata"), rows(ledger.path, "counters")) == before


@pytest.mark.parametrize("state", ["RESERVED", "DISPATCHED", "UNKNOWN"])
def test_inflight_or_unknown_requests_block_amendment_without_releasing_hold(tmp_path, state):
    ledger = open_budget(tmp_path / "original.sqlite3")
    identity, _ = reserve(ledger, "pending", 16384)
    if state != "RESERVED":
        ledger.mark_dispatched(identity)
    ledger.halt(reason=V6_REVIEW_AMENDMENT_PAUSE, invocation_id="authorized")
    if state == "UNKNOWN":
        ledger.unknown(identity, reason="inflight timeout after pause")
    before = ledger.snapshot()
    with pytest.raises(BudgetAmendmentError, match="settle|another halt"):
        amendment(ledger)
    assert ledger.snapshot() == before
    assert ledger.request_record(identity)["state"] == state


@pytest.mark.parametrize("column", ["held", "pending", "unknown", "spent"])
def test_inconsistent_counters_are_not_reconstructed_during_amendment(tmp_path, column):
    ledger, _ = paused_budget(tmp_path / "original.sqlite3")
    with sqlite3.connect(ledger.path) as db:
        db.execute(f"UPDATE counters SET {column}={column}+1 WHERE singleton=1")
    before = rows(ledger.path, "counters")
    with pytest.raises(BudgetAmendmentError, match="conserve"):
        amendment(ledger)
    assert rows(ledger.path, "counters") == before


def test_missing_original_database_and_non_v6_ledger_cannot_be_amended(tmp_path):
    missing = tmp_path / "does-not-exist" / "original.sqlite3"
    with pytest.raises(BudgetAmendmentError, match="missing"):
        apply_v6_review_amendment(
            missing,
            expected_run_id="lost",
            expected_config_sha256="0" * 64,
            amendment_id=AMENDMENT,
            allowed_review_output_limits=CAPS,
            evidence={"authorized": True},
        )
    with pytest.raises(BudgetAmendmentError, match="missing"):
        reopen(missing)
    assert not missing.parent.exists()
    legacy = open_budget(tmp_path / "legacy.sqlite3", purpose=PURPOSE, max_output_tokens=2048)
    legacy.halt(reason=V6_REVIEW_AMENDMENT_PAUSE, invocation_id="not-v6")
    with pytest.raises(BudgetAmendmentError, match="V6"):
        amendment(legacy)


def test_amendment_is_atomic_if_durable_audit_event_cannot_be_appended(tmp_path):
    ledger, _ = paused_budget(tmp_path / "original.sqlite3")
    before = {
        name: rows(ledger.path, name) for name in ("metadata", "requests", "counters", "events")
    }
    with sqlite3.connect(ledger.path) as db:
        db.execute(
            "CREATE TRIGGER fail_amendment BEFORE INSERT ON events "
            "WHEN NEW.action='v6_review_capacity_amended' "
            "BEGIN SELECT RAISE(ABORT, 'fixture audit event failure'); END"
        )
    with pytest.raises(sqlite3.IntegrityError, match="audit event failure"):
        amendment(ledger)
    assert {name: rows(ledger.path, name) for name in before} == before


def test_concurrent_amendment_cannot_apply_twice(tmp_path):
    ledger, _ = paused_budget(tmp_path / "original.sqlite3")

    def attempt(_):
        try:
            return amendment(ledger)
        except BudgetAmendmentError:
            return None

    with ThreadPoolExecutor(max_workers=2) as executor:
        results = list(executor.map(attempt, range(2)))
    assert sum(result is not None for result in results) == 1
    assert sum(row[2] == V6_REVIEW_AMENDMENT_ACTION for row in rows(ledger.path, "events")) == 1
    assert reopen(ledger.path).snapshot()["requests_reserved"] == 2


def test_explicit_open_requires_immutable_amendment_evidence_and_never_recreates_lost_db(tmp_path):
    ledger, _ = paused_budget(tmp_path / "original.sqlite3")
    amendment(ledger)
    with sqlite3.connect(ledger.path) as db:
        row = db.execute(
            "SELECT value FROM metadata WHERE key=?", ("v6_review_amendment:" + AMENDMENT,)
        ).fetchone()
        changed = copy.deepcopy(json.loads(row[0]))
        changed["new_config_sha256"] = "0" * 64
        db.execute(
            "UPDATE metadata SET value=? WHERE key=?",
            (json.dumps(changed), "v6_review_amendment:" + AMENDMENT),
        )
    with pytest.raises(BudgetAmendmentError, match="authorization"):
        reopen(ledger.path)
    ledger.path.rename(tmp_path / "retained-original.sqlite3")
    with pytest.raises(BudgetAmendmentError, match="missing"):
        reopen(ledger.path)
    assert not ledger.path.exists()
