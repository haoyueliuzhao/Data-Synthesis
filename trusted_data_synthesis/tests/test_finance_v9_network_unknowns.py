"""Finite network terminal acknowledgement on synthetic SQLite; no real HTTP."""

import json
import sqlite3

import pytest
from test_finance_unknown_abandonment import table
from test_finance_v9_monetary_amendment import apply
from test_finance_v9_monetary_amendment import synthetic_parent as synthetic_parent
from test_finance_v9_monetary_amendment import wallet as wallet

from trusted_synthesis.finance_research.contracts import digest, invocation_identity
from trusted_synthesis.finance_research.probe_budget import (
    UNKNOWN_ABANDONMENT_ACTION,
    V9_NETWORK_PROTOCOL_ID,
    V9_NETWORK_UNKNOWN_REASON,
    DuplicateInvocation,
    UnknownAbandonmentError,
    read_budget_snapshot,
)


def authority(**changes):
    body = dict(
        schema="v9_network_unknown_terminal_authorization.v1",
        user_reply="允许上述有限修订并继续同一矩阵",
        protocol_id=V9_NETWORK_PROTOCOL_ID,
        risk_acknowledged=True,
        no_resend=True,
        permanent_full_hold=True,
        hard_cap_microcny=1200000000,
        scope_all_same_matrix_connection_interruptions=True,
        unknown_never_positive=True,
        terminal_completion_semantics=(
            "all registered jobs have authentic terminal records; "
            "actual returned responses counted separately"
        ),
    )
    body.update(changes)
    return {**body, "id": digest(body)}


@pytest.fixture
def network_wallet(wallet):
    ledger, old_unknown, held = wallet
    apply(ledger)
    return ledger, old_unknown, held


def attempts(
    ledger,
    *,
    names=("a", "b"),
    exceptions=None,
    response=False,
    reason=V9_NETWORK_UNKNOWN_REASON,
    dispatched=True,
):
    expected, pending = {}, []
    for name in names:
        job = "slot:" + digest(name)
        episode = "v8prod:" + digest(dict(protocol_id=V9_NETWORK_PROTOCOL_ID, job_key=job))
        coords = invocation_identity(
            dict(run_id=ledger.run_id, episode_id=episode, attempt_index=1), turn_index=0
        )
        body = dict(model="deepseek-flash", max_tokens=16384, thinking={"type": "disabled"})
        iid = coords["invocation_id"]
        ledger.reserve(
            iid, coordinates=coords, request=body, request_body=json.dumps(body).encode()
        )
        if dispatched:
            ledger.mark_dispatched(iid)
        pending.append((iid, coords, body))
        expected[iid] = dict(job_key=job, request_sha256=digest(body))
    # All calls are first dispatched, then independently fail: genuine multi-halt case.
    for index, (iid, coords, body) in enumerate(pending):
        evidence = dict(
            budget_invocation_id=iid,
            budget_coordinates=coords,
            request_sha256=digest(body),
            wire_protocol="v8_single_target_review.v1",
            service_response_received=response,
            exception_type=(exceptions or ["RemoteProtocolError"] * len(pending))[index],
        )
        ledger.unknown(iid, reason=reason, evidence=evidence)
    return expected


def acknowledge(ledger, expected, **changes):
    args = dict(
        protocol_id=V9_NETWORK_PROTOCOL_ID, authorization=authority(), expected_requests=expected
    )
    args.update(changes)
    return ledger.acknowledge_v9_connection_unknowns(**args)


def test_multiple_unknowns_keep_every_row_hold_and_return_each_original_binding(network_wallet):
    ledger, historic_unknown, historic_held = network_wallet
    expected = attempts(ledger)
    before = read_budget_snapshot(ledger.path)
    original = {
        name: table(ledger.path, name) for name in ("requests", "counters", "v8_request_quotas")
    }
    receipt = acknowledge(ledger, expected)
    after = read_budget_snapshot(ledger.path)
    assert receipt["new_acknowledgements"] == 2
    assert {r["invocation_id"] for r in receipt["records"]} == set(expected)
    assert all(r["protocol_id"] == V9_NETWORK_PROTOCOL_ID for r in receipt["records"])
    assert all(
        r["network_terminal_authorization_id"] == authority()["id"] for r in receipt["records"]
    )
    assert all(r["permanent_reserved_microcny"] == 2228224 for r in receipt["records"])
    assert all(
        not r["actual_usage_known"] and not r["reservation_released"] for r in receipt["records"]
    )
    assert all(table(ledger.path, name) == rows for name, rows in original.items())
    assert before["config_sha256"] == after["config_sha256"]
    assert (
        after["snapshot"]["held_microcny"]
        == before["snapshot"]["held_microcny"]
        == historic_held + 2 * 2228224
    )
    assert (
        after["snapshot"]["settled_tariff_microcny"]
        == before["snapshot"]["settled_tariff_microcny"]
    )
    assert (
        after["snapshot"]["unknown_requests"]
        == after["snapshot"]["acknowledged_unknown_requests"]
        == 3
    )
    assert after["snapshot"]["unacknowledged_unknown_requests"] == 0
    assert after["snapshot"]["halt"] is None
    assert len(ledger.unsettled()) == 3 and ledger.blocking_unsettled() == []
    assert (
        next(r for r in before["acknowledged_unknowns"] if r["invocation_id"] == historic_unknown)
        in after["acknowledged_unknowns"]
    )
    saved = {name: table(ledger.path, name) for name in ("metadata", "events")}
    assert acknowledge(ledger, expected) == receipt
    assert all(table(ledger.path, name) == rows for name, rows in saved.items())
    iid = next(iter(expected))
    row = ledger.request_record(iid)
    with pytest.raises(DuplicateInvocation):
        ledger.reserve(
            iid,
            coordinates=json.loads(row["coordinates_json"]),
            request=json.loads(row["request_body"]),
            request_body=row["request_body"],
        )


def test_same_authority_covers_later_same_matrix_errors_without_rewriting_old_acks(network_wallet):
    ledger, _, _ = network_wallet
    first = attempts(ledger, names=("one",))
    old = acknowledge(ledger, first)
    later = attempts(ledger, names=("two",), exceptions=["ReadTimeout"])
    combined = {**first, **later}
    receipt = acknowledge(ledger, combined)
    assert receipt["new_acknowledgements"] == 1
    assert old["records"][0] in receipt["records"]
    events = table(ledger.path, "events")
    assert sum(row[2] == UNKNOWN_ABANDONMENT_ACTION for row in events) == 3  # Historical + two.
    read_only = acknowledge(ledger, later)  # Reassemble subset without new financial events.
    assert read_only["lookup_only"] and read_only["new_acknowledgements"] == 0
    assert table(ledger.path, "events") == events
    ledger.halt(reason="later unrelated pause", invocation_id="other")
    assert acknowledge(ledger, combined) == receipt
    assert ledger.snapshot()["halt"]["reason"] == "later unrelated pause"


@pytest.mark.parametrize(
    "exception", ["CancelledError", "PoolTimeout", "ValueError", "HTTPStatusError"]
)
def test_other_failure_categories_not_covered_by_connection_authority(network_wallet, exception):
    ledger, _, _ = network_wallet
    expected = attempts(ledger, exceptions=["RemoteProtocolError", exception])
    before = {
        name: table(ledger.path, name) for name in ("requests", "counters", "metadata", "events")
    }
    with pytest.raises(UnknownAbandonmentError, match="approved no-response"):
        acknowledge(ledger, expected)
    assert all(table(ledger.path, name) == rows for name, rows in before.items())


@pytest.mark.parametrize(
    "failure",
    [
        "received",
        "usage_reason",
        "wrong_hash",
        "wrong_job",
        "partial",
        "pending",
        "unrelated_halt",
        "undispatched",
    ],
)
def test_batch_exact_binding_and_quiescent_complete_scope(network_wallet, failure):
    ledger, _, _ = network_wallet
    if failure == "pending":
        from test_finance_v6_probe_budget import reserve

        reserve(ledger, "v8prod:pending", 16384)
    expected = attempts(
        ledger,
        response=failure == "received",
        dispatched=failure != "undispatched",
        reason="invalid_or_interrupted_response"
        if failure == "usage_reason"
        else V9_NETWORK_UNKNOWN_REASON,
    )
    iid = next(iter(expected))
    if failure == "wrong_hash":
        expected[iid]["request_sha256"] = "0" * 64
    elif failure == "wrong_job":
        expected[iid]["job_key"] = "slot:different"
    elif failure == "partial":
        expected.pop(iid)
    elif failure == "unrelated_halt":
        # INSERT OR IGNORE retains the earlier network halt; the later event must still block.
        ledger.halt(reason="unrelated actor pause", invocation_id="other")
    before = {
        name: table(ledger.path, name) for name in ("requests", "counters", "metadata", "events")
    }
    with pytest.raises(UnknownAbandonmentError):
        acknowledge(ledger, expected)
    assert all(table(ledger.path, name) == rows for name, rows in before.items())


def test_wrong_authorization_or_historical_unknown_cannot_be_swept_in(network_wallet):
    ledger, historic, _ = network_wallet
    expected = attempts(ledger, names=("new",))
    with pytest.raises(UnknownAbandonmentError, match="authority"):
        acknowledge(ledger, expected, authorization=authority(no_resend=False))
    expected[historic] = dict(
        job_key="old-history", request_sha256=ledger.request_record(historic)["request_sha256"]
    )
    with pytest.raises(UnknownAbandonmentError):
        acknowledge(ledger, expected)
    assert ledger.snapshot()["unacknowledged_unknown_requests"] == 1


def test_counter_mismatch_rolls_back_all_acknowledgements(network_wallet):
    ledger, _, _ = network_wallet
    expected = attempts(ledger)
    with sqlite3.connect(ledger.path) as db:
        db.execute("UPDATE counters SET spent=spent+1")
    before = table(ledger.path, "metadata")
    with pytest.raises(UnknownAbandonmentError, match="accounting"):
        acknowledge(ledger, expected)
    assert table(ledger.path, "metadata") == before
