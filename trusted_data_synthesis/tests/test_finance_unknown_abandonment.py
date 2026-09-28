"""Auditable UNKNOWN abandonment only in temporary SQLite; no real HTTP/billing."""

import json
import sqlite3

import pytest
from test_finance_research_probe_budget import sheet, usage
from test_finance_v6_probe_budget import reserve, settle

from trusted_synthesis.finance_research.probe_budget import (
    UNKNOWN_ABANDONMENT_ACTION,
    UNKNOWN_ABANDONMENT_PREFIX,
    V6_PURPOSE,
    BudgetUnavailable,
    DuplicateInvocation,
    ProbeBudget,
    UnknownAbandonmentError,
    read_budget_snapshot,
)

REASON = "review transport response or billing usage unknown"


def fixture(tmp_path, **limits):
    ledger = ProbeBudget(
        tmp_path / "original.sqlite3",
        run_id="original-joint-run",
        price_sheet=sheet(),
        max_output_tokens=16384,
        purpose=V6_PURPOSE,
        **limits,
    )
    paid, _ = reserve(ledger, "settled-before-unknown", 2048)
    settle(ledger, paid, 20)
    interrupted, held = reserve(ledger, "abandoned-original-call", 16384)
    ledger.mark_dispatched(interrupted)
    ledger.unknown(interrupted, reason=REASON, evidence={"exception_type": "CancelledError"})
    return ledger, interrupted, held


def acknowledge(ledger, invocation_id, **changes):
    args = dict(
        authorization_id="explicit-user-budget-disposition-01",
        expected_request_sha256=ledger.request_record(invocation_id)["request_sha256"],
        expected_halt_reason=REASON,
        reason="Continue within original cap with maximum hold retained",
        evidence={
            "user_message": "预算充足，整体仍有七百左右的预算",
            "policy": "retain whole worst-case reservation, no invoice claim and no retry",
        },
    )
    args.update(changes)
    return ledger.acknowledge_unknown_abandonment(invocation_id, **args)


def table(path, name):
    with sqlite3.connect(path) as db:
        return db.execute(f"SELECT * FROM {name} ORDER BY 1").fetchall()


def test_abandonment_keeps_full_unknown_row_all_counters_and_original_exposure(tmp_path):
    ledger, iid, held = fixture(tmp_path)
    before_rows, before_counters = table(ledger.path, "requests"), table(ledger.path, "counters")
    before_events, before = table(ledger.path, "events"), ledger.snapshot()
    record = acknowledge(ledger, iid)
    after = ledger.snapshot()
    assert held == record["permanent_reserved_microcny"] == 2_228_224
    assert table(ledger.path, "requests") == before_rows
    assert table(ledger.path, "counters") == before_counters
    assert table(ledger.path, "events")[:-1] == before_events
    assert table(ledger.path, "events")[-1][2] == UNKNOWN_ABANDONMENT_ACTION
    assert after["unknown_requests"] == 1 and after["acknowledged_unknown_requests"] == 1
    assert after["unacknowledged_unknown_requests"] == 0
    assert after["acknowledged_unknown_held_microcny"] == after["held_microcny"] == held
    assert after["settled_tariff_microcny"] == before["settled_tariff_microcny"] == 280
    assert after["exposure_microcny"] == before["exposure_microcny"] == held + 280
    assert after["remaining_exposure_microcny"] == 800_000_000 - held - 280
    assert after["halt"] is None and ledger.request_record(iid)["usage_json"] is None
    assert ledger.request_record(iid)["state"] == "UNKNOWN"
    assert ledger.unsettled()[0]["invocation_id"] == iid and ledger.blocking_unsettled() == []
    assert not record["actual_charge_known"] and not record["reservation_released"]
    assert not record["retry_authorized"] and not record["replacement_call_authorized"]


def test_future_calls_may_progress_but_abandoned_call_cannot_ever_retry_or_settle(tmp_path):
    ledger, iid, held = fixture(tmp_path)
    acknowledge(ledger, iid)
    new, _ = reserve(ledger, "different-authorized-future-work", 2048)
    settle(ledger, new, 30)
    assert ledger.snapshot()["held_microcny"] == held
    with pytest.raises(DuplicateInvocation):
        reserve(ledger, "abandoned-original-call", 16384)
    with pytest.raises(DuplicateInvocation):
        ledger.mark_dispatched(iid)
    with pytest.raises(ValueError, match="dispatched"):
        ledger.settle(
            iid,
            usage=usage(),
            http_status=200,
            response_classification="model_response",
            response_body=b"{}",
        )
    assert (
        ledger.snapshot()["requests_reserved"] == 3
        and ledger.request_record(iid)["state"] == "UNKNOWN"
    )


def test_maximum_hold_still_counts_toward_hard_cap_after_acknowledgement(tmp_path):
    # A smaller registered temporary cap makes the same exposure rule testable with two rows.
    ledger, iid, held = fixture(tmp_path, hard_cap_microcny=3_000_000, warning_microcny=2_500_000)
    acknowledge(ledger, iid)
    with pytest.raises(BudgetUnavailable, match="exceeds"):
        reserve(ledger, "would-exceed-exposure", 2048)
    assert ledger.snapshot()["held_microcny"] == held
    assert ledger.snapshot()["exposure_microcny"] < ledger.snapshot()["hard_cap_microcny"]


def test_exact_authorization_is_idempotent_and_never_clears_a_later_unrelated_halt(tmp_path):
    ledger, iid, _ = fixture(tmp_path)
    record = acknowledge(ledger, iid)
    events = table(ledger.path, "events")
    assert acknowledge(ledger, iid) == record and table(ledger.path, "events") == events
    ledger.halt(reason="separate user pause", invocation_id="other-scope")
    before = ledger.snapshot()
    assert acknowledge(ledger, iid) == record
    assert ledger.snapshot() == before and before["halt"]["reason"] == "separate user pause"
    with pytest.raises(BudgetUnavailable):
        reserve(ledger, "still-paused", 2048)


@pytest.mark.parametrize(
    "changes",
    [
        dict(authorization_id=""),
        dict(evidence={}),
        dict(expected_request_sha256="0" * 64),
        dict(expected_halt_reason="different reason"),
    ],
)
def test_missing_authority_or_wrong_exact_binding_keeps_pause_and_hold(tmp_path, changes):
    ledger, iid, _ = fixture(tmp_path)
    before = {
        name: table(ledger.path, name) for name in ("metadata", "requests", "counters", "events")
    }
    with pytest.raises(UnknownAbandonmentError):
        acknowledge(ledger, iid, **changes)
    assert {name: table(ledger.path, name) for name in before} == before


def test_acknowledged_invocation_cannot_be_reauthorized_with_changed_evidence(tmp_path):
    ledger, iid, _ = fixture(tmp_path)
    acknowledge(ledger, iid)
    with pytest.raises(UnknownAbandonmentError, match="different authorization"):
        acknowledge(ledger, iid, authorization_id="another-authority")
    with pytest.raises(UnknownAbandonmentError, match="different authorization"):
        acknowledge(ledger, iid, reason="claim fee was zero")


def test_hidden_later_halt_is_not_cleared_by_unknown_abandonment(tmp_path):
    ledger, iid, _ = fixture(tmp_path)
    ledger.halt(reason="unrelated failure", invocation_id="other-request")
    assert (
        ledger.snapshot()["halt"]["invocation_id"] == iid
    )  # INSERT OR IGNORE retained first halt.
    before = ledger.snapshot()
    with pytest.raises(UnknownAbandonmentError, match="unrelated later halt"):
        acknowledge(ledger, iid)
    assert ledger.snapshot() == before


def test_only_original_unknown_transition_halt_may_clear_even_for_same_invocation(tmp_path):
    ledger, iid, _ = fixture(tmp_path)
    with sqlite3.connect(ledger.path) as db:
        db.execute(
            "DELETE FROM metadata WHERE key='halt'"
        )  # Only this temporary corruption control.
    ledger.halt(reason="different administrative stop", invocation_id=iid)
    with pytest.raises(UnknownAbandonmentError, match="unrelated halt"):
        acknowledge(ledger, iid, expected_halt_reason="different administrative stop")
    assert ledger.snapshot()["halt"]["reason"] == "different administrative stop"


def test_new_unacknowledged_unknown_still_blocks_after_an_older_ack(tmp_path):
    ledger, iid, _ = fixture(tmp_path)
    acknowledge(ledger, iid)
    next_id, _ = reserve(ledger, "new-unknown", 2048)
    ledger.mark_dispatched(next_id)
    ledger.unknown(next_id, reason="new uncertain outcome")
    state = ledger.snapshot()
    assert state["unknown_requests"] == 2 and state["acknowledged_unknown_requests"] == 1
    assert state["unacknowledged_unknown_requests"] == 1
    assert [r["invocation_id"] for r in ledger.blocking_unsettled()] == [next_id]
    with pytest.raises(BudgetUnavailable):
        reserve(ledger, "must-stop-again", 2048)


def test_registry_or_original_unknown_mutation_blocks_read_and_reserve(tmp_path):
    ledger, iid, _ = fixture(tmp_path)
    acknowledge(ledger, iid)
    with sqlite3.connect(ledger.path) as db:
        db.execute(
            "UPDATE requests SET reserved_microcny=reserved_microcny-1 WHERE invocation_id=?",
            (iid,),
        )
    with pytest.raises(UnknownAbandonmentError, match="original held"):
        ledger.snapshot()
    with pytest.raises(UnknownAbandonmentError):
        reserve(ledger, "cannot-erase-hold", 2048)


def test_abandonment_rolls_back_if_authorization_event_cannot_persist(tmp_path):
    ledger, iid, _ = fixture(tmp_path)
    before = {
        name: table(ledger.path, name) for name in ("metadata", "requests", "counters", "events")
    }
    with sqlite3.connect(ledger.path) as db:
        db.execute(
            "CREATE TRIGGER fail_ack BEFORE INSERT ON events WHEN NEW.action="
            "'unknown_abandonment_acknowledged' BEGIN "
            "SELECT RAISE(ABORT, 'fixture event failure'); END"
        )
    with pytest.raises(sqlite3.IntegrityError, match="event failure"):
        acknowledge(ledger, iid)
    assert {name: table(ledger.path, name) for name in before} == before


def test_read_only_registration_snapshot_exposes_unknowns_without_creating_or_mutating(tmp_path):
    missing = tmp_path / "not-created.sqlite3"
    with pytest.raises(UnknownAbandonmentError, match="missing"):
        read_budget_snapshot(missing)
    assert not missing.exists()
    ledger, iid, held = fixture(tmp_path)
    record = acknowledge(ledger, iid)
    before = {
        name: table(ledger.path, name) for name in ("metadata", "requests", "counters", "events")
    }
    snapshot = read_budget_snapshot(ledger.path)
    assert snapshot["read_only"] and snapshot["config"] == ledger.config
    assert snapshot["snapshot"] == ledger.snapshot()
    assert snapshot["request_counts_by_state"] == {"SETTLED": 1, "UNKNOWN": 1}
    assert snapshot["acknowledged_unknowns"] == [record]
    assert snapshot["snapshot"]["acknowledged_unknown_held_microcny"] == held
    assert {name: table(ledger.path, name) for name in before} == before
    with sqlite3.connect(ledger.path) as db:
        saved = json.loads(
            db.execute(
                "SELECT value FROM metadata WHERE key=?", (UNKNOWN_ABANDONMENT_PREFIX + iid,)
            ).fetchone()[0]
        )
    assert saved == record
