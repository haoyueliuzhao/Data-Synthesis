"""V10 dual caps and recovery on copied synthetic SQLite; no API/real wallet."""

import json
import sqlite3
from concurrent.futures import ThreadPoolExecutor

import pytest
from test_finance_research_probe_budget import usage
from test_finance_unknown_abandonment import table
from test_finance_v6_probe_budget import reserve, settle
from test_finance_v9_monetary_amendment import apply, synthetic_parent  # noqa: F401

from trusted_synthesis.finance_research.contracts import digest, invocation_identity
from trusted_synthesis.finance_research.probe_budget import (
    UNKNOWN_ABANDONMENT_ACTION,
    UNKNOWN_ABANDONMENT_PREFIX,
    BudgetUnavailable,
    DuplicateInvocation,
    InvalidUsage,
    RequestPartitionError,
    UnknownAbandonmentError,
    _json,
    _request_record_digest,
)
from trusted_synthesis.finance_research.v10_budget import (
    BATCH_ID,
    HISTORY,
    LIMITS,
    NETWORK_REASON,
    acknowledge_connection_unknowns,
    continue_reserved,
    generation_episode_id,
    map_episode_id,
    open_budget,
    preflight,
    register_v10_batch,
    review_episode_id,
)

SLOTS = [
    dict(
        task_id=f"synthetic-public-{i}",
        slot_index=j,
        slot_id=generation_episode_id(BATCH_ID, f"synthetic-public-{i}", j),
        purpose="common_material_candidate",
    )
    for i in range(1000)
    for j in range(8)
]


@pytest.fixture(scope="module")
def stopped_history(tmp_path_factory, synthetic_parent):  # noqa: F811
    path = tmp_path_factory.mktemp("synthetic-v10-history") / "wallet.sqlite"
    with sqlite3.connect(synthetic_parent[0]) as source, sqlite3.connect(path) as target:
        source.backup(target)
    ledger = open_budget(path)
    apply(ledger)
    with sqlite3.connect(path) as db:
        db.row_factory = sqlite3.Row
        paid = dict(db.execute("SELECT * FROM requests WHERE state='SETTLED' LIMIT 1").fetchone())
        unknown = dict(
            db.execute("SELECT * FROM requests WHERE state='UNKNOWN' LIMIT 1").fetchone()
        )
        columns = list(paid)
        rows, allocations, unknown_ids = [], [], []
        for index in range(4740):
            coords = invocation_identity(
                dict(run_id=ledger.run_id, episode_id=f"v8prod:history-{index}", attempt_index=1),
                turn_index=0,
            )
            row = dict(
                unknown if index < 64 else paid,
                invocation_id=coords["invocation_id"],
                coordinates_json=_json(coords),
            )
            rows.append(tuple(row[k] for k in columns))
            allocations.append((coords["invocation_id"], "production_review", coords["episode_id"]))
            if index < 64:
                unknown_ids.append(coords["invocation_id"])
        db.executemany(
            f"INSERT INTO requests({','.join(columns)}) VALUES ({','.join('?' for _ in columns)})",
            rows,
        )
        db.executemany("INSERT INTO v8_request_allocations VALUES (?,?,?)", allocations)
        db.execute("UPDATE v8_request_quotas SET consumed=4740 WHERE category='production_review'")
        paid_sum = db.execute("SELECT SUM(settled_microcny) FROM requests").fetchone()[0]
        # Explicit synthetic accounting adjustment, not purported paid usage.
        db.execute(
            "UPDATE requests SET settled_microcny=settled_microcny+? WHERE invocation_id=?",
            (HISTORY["spent"] - paid_sum, paid["invocation_id"]),
        )
        db.execute(
            "UPDATE counters SET requests=40076,dispatched=40076,"
            "spent=?,held=?,unknown=65,pending=0",
            (HISTORY["spent"], HISTORY["held"]),
        )
        for iid in unknown_ids:
            row = db.execute("SELECT * FROM requests WHERE invocation_id=?", (iid,)).fetchone()
            record = dict(
                schema="synthetic_prior_ack.v1",
                run_id=ledger.run_id,
                invocation_id=iid,
                expected_request_sha256=row["request_sha256"],
                permanent_reserved_microcny=row["reserved_microcny"],
                original_unknown_record_sha256=_request_record_digest(row),
            )
            record["id"] = digest(record)
            db.execute(
                "INSERT INTO metadata VALUES (?,?)",
                (UNKNOWN_ABANDONMENT_PREFIX + iid, _json(record)),
            )
            db.execute(
                "INSERT INTO events(invocation_id,action,payload_json,at_unix) VALUES (?,?,?,0)",
                (iid, UNKNOWN_ABANDONMENT_ACTION, _json(record)),
            )
    assert preflight(path)["snapshot"]["requests_reserved"] == 40076
    return path


@pytest.fixture
def wallet(tmp_path, stopped_history):
    path = tmp_path / "v10-test.sqlite"
    with sqlite3.connect(stopped_history) as source, sqlite3.connect(path) as target:
        source.backup(target)
    return open_budget(path)


def register(ledger, **changes):
    args = dict(
        expected_run_id=ledger.run_id,
        expected_config_sha256=digest(ledger.config),
        batch_id=BATCH_ID,
        generation_slots=SLOTS,
        evidence={"user_authorization": "synthetic prospective audit authorization"},
    )
    args.update(changes)
    return register_v10_batch(ledger.path, **args)


def args(ledger, episode=None, output=2048, turn=0, attempt=1):
    coordinates = invocation_identity(
        dict(
            run_id=ledger.run_id, episode_id=episode or SLOTS[0]["slot_id"], attempt_index=attempt
        ),
        turn_index=turn,
    )
    request = dict(model="deepseek-flash", max_tokens=output, thinking={"type": "disabled"})
    return dict(
        invocation_id=coordinates["invocation_id"],
        coordinates=coordinates,
        request=request,
        request_body=json.dumps(request).encode(),
    )


def connection_unknown(ledger, request, *, exception="ReadError", reason=NETWORK_REASON, **changes):
    ledger.reserve(**request)
    iid = request["invocation_id"]
    ledger.mark_dispatched(iid)
    evidence = dict(
        exception_type=exception,
        service_response_received=False,
        budget_invocation_id=iid,
        budget_coordinates=request["coordinates"],
        request_sha256=digest(request["request"]),
    )
    evidence.update(changes)
    ledger.unknown(iid, reason=reason, evidence=evidence)
    return {iid: digest(request["request"])}


def test_registration_preserves_original_rows_config_unknowns_and_exact_remaining(wallet):
    before = {
        k: table(wallet.path, k)
        for k in ("requests", "counters", "v8_request_quotas", "v8_request_allocations")
    }
    old = preflight(wallet.path)
    record = register(wallet)
    now = preflight(wallet.path)
    assert all(table(wallet.path, k) == rows for k, rows in before.items())
    assert now["config"] == old["config"]
    assert now["acknowledged_unknowns"] == old["acknowledged_unknowns"]
    assert register(wallet) == record
    part = now["snapshot"]["v10_partition"]
    assert part["limits"] == LIMITS
    assert part["unallocated_requests"] == 1924 and part["unallocated_microcny"] == 68_901_111
    assert not part["unallocated_spendable"] and not part["original_950_buffer_spendable"]
    assert now["snapshot"]["effective_hard_cap_microcny"] == 1_200_000_000
    assert now["snapshot"]["warning_microcny"] == 700_000_000
    assert now["snapshot"]["unknown_requests"] == 65
    with sqlite3.connect(wallet.path) as db:
        assert db.execute(
            "SELECT kind,COUNT(*) FROM v10_episode_roster GROUP BY kind ORDER BY kind"
        ).fetchall() == [("generation", 8000), ("mapping", 1000), ("review", 16000)]


@pytest.mark.parametrize("case", ["slots", "authority", "config", "history", "halt", "pending"])
def test_registration_rejects_invalid_or_nonquiescent_scope_without_mutation(wallet, case):
    changes = {}
    if case == "slots":
        changes["generation_slots"] = SLOTS[:-1]
    if case == "authority":
        changes["evidence"] = {}
    if case == "config":
        changes["expected_config_sha256"] = "0" * 64
    if case == "history":
        with sqlite3.connect(wallet.path) as db:
            db.execute("UPDATE counters SET spent=spent+1")
    if case == "halt":
        wallet.halt(reason="separate stop", invocation_id="stop")
    if case == "pending":
        reserve(wallet, "v8prod:old-unsent", 2048)
    before = {k: table(wallet.path, k) for k in ("metadata", "events", "requests", "counters")}
    with pytest.raises(RequestPartitionError):
        register(wallet, **changes)
    assert all(table(wallet.path, k) == rows for k, rows in before.items())


def test_exact_namespaces_new_small_caps_and_request_specific_settlement(wallet):
    register(wallet)
    for episode in (
        "v7-slot:synthetic-0000",
        "v8prod:old",
        "v8review:old",
        "buffer:950",
        "v10gen:fake",
    ):
        with pytest.raises((BudgetUnavailable, DuplicateInvocation)):
            reserve(wallet, episode, 2048)
    with pytest.raises(BudgetUnavailable):
        wallet.reserve(**args(wallet, episode="v7-slot:synthetic-0000", turn=3))
    with pytest.raises(ValueError):
        reserve(wallet, SLOTS[0]["slot_id"], 4096)
    for reviewer, cap in (("A", 4096), ("B", 8192)):
        iid, _ = reserve(wallet, review_episode_id(BATCH_ID, SLOTS[0]["slot_id"], reviewer), cap)
        settle(wallet, iid, cap)
    mapping = map_episode_id(BATCH_ID, SLOTS[0]["task_id"])
    iid, _ = reserve(wallet, mapping, 65536)
    wallet.mark_dispatched(iid)
    with pytest.raises(InvalidUsage):
        wallet.settle(
            iid,
            usage=usage(output=65537),
            http_status=200,
            response_classification="model_response",
            response_body=b"{}",
        )
    wallet.settle(
        iid,
        usage=usage(output=40000),
        http_status=200,
        response_classification="model_response",
        response_body=b"{}",
    )
    quota = wallet.snapshot()["v10_partition"]["consumed"]["review_mapping"]
    assert quota["requests"] == quota["dispatched"] == 3
    assert quota["held"] == quota["pending"] == 0
    assert 4096 not in wallet.config["allowed_output_limits"]


def test_old_scope_cannot_use_new_cap_before_registration(wallet):
    with pytest.raises(ValueError):
        reserve(wallet, "v8prod:old", 4096)


def test_concurrent_generation_money_cap_and_no_borrowing(wallet):
    register(wallet)

    def one(index):
        try:
            return reserve(wallet, SLOTS[index]["slot_id"], 2048)
        except BudgetUnavailable:
            return None

    with ThreadPoolExecutor(max_workers=8) as workers:
        outcomes = list(workers.map(one, range(56)))
    accepted = [r for r in outcomes if r]
    assert len(accepted) == 100_000_000 // 2_113_536 == 47
    state = wallet.snapshot()
    assert state["v10_partition"]["consumed"]["generation"]["held"] == 47 * 2_113_536
    # Separate review capacity still exists; neither family borrows the other's money.
    ri, _ = reserve(wallet, review_episode_id(BATCH_ID, SLOTS[0]["slot_id"], "A"), 4096)
    settle(wallet, ri, 20)
    settle(wallet, accepted[0][0], 20)
    reserve(wallet, SLOTS[57]["slot_id"], 2048)
    assert wallet.snapshot()["v10_partition"]["consumed"]["generation"]["requests"] == 48


@pytest.mark.parametrize("category", ["generation", "review_mapping"])
def test_atomic_request_sublimit_boundary_uses_same_admission(wallet, category):
    register(wallet)
    limit = LIMITS[category]["requests"]
    # Compact synthetic counter fixture at the real cap boundary. No fabricated API results.
    with sqlite3.connect(wallet.path) as db:
        db.execute(
            "UPDATE v10_quotas SET requests=?,dispatched=? WHERE category=?",
            (limit - 1, limit - 1, category),
        )
        db.execute(
            "UPDATE counters SET requests=requests+?,dispatched=dispatched+?",
            (limit - 1, limit - 1),
        )

    def one(index):
        try:
            sid = SLOTS[index]["slot_id"]
            return reserve(
                wallet,
                sid if category == "generation" else review_episode_id(BATCH_ID, sid, "A"),
                2048,
            )
        except BudgetUnavailable:
            return None

    with ThreadPoolExecutor(max_workers=4) as workers:
        outcomes = list(workers.map(one, range(8)))
    assert sum(r is not None for r in outcomes) == 1
    assert wallet.snapshot()["v10_partition"]["consumed"][category]["requests"] == limit
    other = (
        review_episode_id(BATCH_ID, SLOTS[0]["slot_id"], "A")
        if category == "generation"
        else SLOTS[0]["slot_id"]
    )
    reserve(wallet, other, 2048)


@pytest.mark.parametrize("category", ["generation", "review_mapping"])
def test_money_sublimit_counts_settled_usage_alongside_new_hold(wallet, category):
    register(wallet)
    spent = LIMITS[category]["microcny"] - 1
    # Counter-only synthetic boundary, not a purported historical settlement.
    with sqlite3.connect(wallet.path) as db:
        db.execute("UPDATE v10_quotas SET spent=? WHERE category=?", (spent, category))
        db.execute("UPDATE counters SET spent=spent+?", (spent,))
    sid = SLOTS[0]["slot_id"]
    episode = sid if category == "generation" else review_episode_id(BATCH_ID, sid, "A")
    with pytest.raises(BudgetUnavailable, match="money sublimit"):
        reserve(wallet, episode, 2048)


def test_multiple_network_unknowns_must_all_be_bound_after_drain(wallet):
    register(wallet)
    requests = [args(wallet, episode=slot["slot_id"]) for slot in SLOTS[:2]]
    for request in requests:
        wallet.reserve(**request)
        wallet.mark_dispatched(request["invocation_id"])
    expected = {}
    for request in requests:
        iid, coords = request["invocation_id"], request["coordinates"]
        sha = digest(request["request"])
        wallet.unknown(
            iid,
            reason=NETWORK_REASON,
            evidence=dict(
                exception_type="ConnectError",
                service_response_received=False,
                budget_invocation_id=iid,
                budget_coordinates=coords,
                request_sha256=sha,
            ),
        )
        expected[iid] = sha
    with pytest.raises(UnknownAbandonmentError):
        acknowledge_connection_unknowns(
            wallet,
            batch_id=BATCH_ID,
            expected_requests={requests[0]["invocation_id"]: digest(requests[0]["request"])},
        )
    receipt = acknowledge_connection_unknowns(wallet, batch_id=BATCH_ID, expected_requests=expected)
    assert receipt["new_acknowledgements"] == 2 and len(receipt["records"]) == 2
    state = wallet.snapshot()
    assert state["unknown_requests"] == state["acknowledged_unknown_requests"] == 67
    assert state["v10_partition"]["consumed"]["generation"]["held"] == 2 * 2_113_536
    assert state["v10_partition"]["consumed"]["generation"]["unknown"] == 2
    assert state["pending_requests"] == 0


def test_reserved_exact_continuation_does_not_count_again_and_dispatch_once(wallet):
    register(wallet)
    request = args(wallet)
    held = wallet.reserve(**request)
    before = wallet.snapshot()
    assert continue_reserved(wallet, **request) == held
    assert wallet.snapshot() == before
    changed = {**request, "request_body": request["request_body"] + b" "}
    with pytest.raises(DuplicateInvocation):
        continue_reserved(wallet, **changed)
    wallet.mark_dispatched(request["invocation_id"])
    with pytest.raises(DuplicateInvocation):
        continue_reserved(wallet, **request)
    with pytest.raises(DuplicateInvocation):
        wallet.mark_dispatched(request["invocation_id"])


@pytest.mark.parametrize("kind", ["generation", "review", "mapping"])
def test_connection_ack_retains_full_hold_unknown_and_no_material_or_resend(wallet, kind):
    register(wallet)
    sid = SLOTS[0]["slot_id"]
    episode = (
        sid
        if kind == "generation"
        else review_episode_id(BATCH_ID, sid, "A")
        if kind == "review"
        else map_episode_id(BATCH_ID, SLOTS[0]["task_id"])
    )
    request = args(wallet, episode=episode, output=2048 if kind == "generation" else 4096)
    expected = connection_unknown(wallet, request)
    before = {k: table(wallet.path, k) for k in ("requests", "counters", "v10_quotas")}
    receipt = acknowledge_connection_unknowns(wallet, batch_id=BATCH_ID, expected_requests=expected)
    assert all(table(wallet.path, k) == rows for k, rows in before.items())
    record = receipt["records"][0]
    assert record["model_response"] is record["model_usage"] is record["model_result"] is None
    assert not record["material_eligible"] and not record["retry_authorized"]
    assert (
        wallet.snapshot()["unknown_requests"]
        == wallet.snapshot()["acknowledged_unknown_requests"]
        == 66
    )
    assert wallet.snapshot()["halt"] is None
    with pytest.raises(DuplicateInvocation):
        wallet.reserve(**request)
    with pytest.raises(DuplicateInvocation):
        continue_reserved(wallet, **request)
    wallet.halt(reason="later separate halt", invocation_id="other")
    assert (
        acknowledge_connection_unknowns(wallet, batch_id=BATCH_ID, expected_requests=expected)
        == receipt
    )
    assert wallet.snapshot()["halt"]["reason"] == "later separate halt"


@pytest.mark.parametrize(
    "failure", ["pending", "reason", "exception", "service_received", "wrong_hash", "later_halt"]
)
def test_connection_ack_does_not_bypass_non_network_or_partial_set(wallet, failure):
    register(wallet)
    if failure == "pending":
        wallet.reserve(**args(wallet, episode=SLOTS[1]["slot_id"]))
    request = args(wallet)
    expected = connection_unknown(
        wallet,
        request,
        reason="invalid billing format" if failure == "reason" else NETWORK_REASON,
        exception="ValueError" if failure == "exception" else "ReadTimeout",
        service_response_received=failure == "service_received",
    )
    if failure == "wrong_hash":
        expected[request["invocation_id"]] = "0" * 64
    if failure == "later_halt":
        wallet.halt(reason="source binding differs", invocation_id="else")
    before = {k: table(wallet.path, k) for k in ("metadata", "events", "requests", "counters")}
    with pytest.raises(UnknownAbandonmentError):
        acknowledge_connection_unknowns(wallet, batch_id=BATCH_ID, expected_requests=expected)
    assert all(table(wallet.path, k) == rows for k, rows in before.items())


@pytest.mark.parametrize("kind", ["retry", "review_turn", "model"])
def test_no_retry_extra_review_turn_or_other_model(wallet, kind):
    register(wallet)
    request = args(
        wallet,
        attempt=2 if kind == "retry" else 1,
        episode=review_episode_id(BATCH_ID, SLOTS[0]["slot_id"], "B")
        if kind == "review_turn"
        else None,
        turn=1 if kind == "review_turn" else 0,
    )
    if kind == "model":
        request["request"]["model"] = "different-model"
        request["request_body"] = json.dumps(request["request"]).encode()
    with pytest.raises((BudgetUnavailable, ValueError)):
        wallet.reserve(**request)
