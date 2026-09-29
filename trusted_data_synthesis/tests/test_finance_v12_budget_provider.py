"""Temporary SQLite + mock HTTP controls only; no paid/model/CUDA operations."""

import asyncio
import copy
import hashlib
import json
import sqlite3
from concurrent.futures import ThreadPoolExecutor

import httpx
import pytest
from test_finance_research_probe_provider import Client
from test_finance_unknown_abandonment import table
from test_finance_v6_strict_review_provider import response_fixture
from test_finance_v10_budget import SLOTS, register, stopped_history, synthetic_parent  # noqa: F401
from test_finance_v10_funding import apply as fund
from test_finance_v10_process_review import fixture as original_fixture

from trusted_synthesis.finance_research import v12_budget as budget
from trusted_synthesis.finance_research import v12_review_protocol as protocol
from trusted_synthesis.finance_research import v12_review_provider as provider
from trusted_synthesis.finance_research.contracts import (
    ProviderCallError,
    digest,
    invocation_identity,
)
from trusted_synthesis.finance_research.probe_budget import (
    BudgetUnavailable,
    DuplicateInvocation,
    RequestPartitionError,
    UnknownAbandonmentError,
)
from trusted_synthesis.finance_research.providers import _json
from trusted_synthesis.finance_research.v10_budget import open_budget, review_episode_id
from trusted_synthesis.finance_research.v12_review_registration import CONCURRENCY

PROTOCOL_ID = "CPU-ONLY-new-V12-matrix"
KEY = "CPU-key-no-real-credential"


def clone(source, path):
    with sqlite3.connect(source) as a, sqlite3.connect(path) as b:
        a.backup(b)
    return open_budget(path)


def plan_and_request():
    episode, original, _ = original_fixture()
    episode = episode.model_copy(update={"task_id": SLOTS[0]["task_id"]})
    request = protocol.prepare_request(
        episode,
        slot_id=SLOTS[0]["slot_id"],
        role="A",
        native_result=original["native_result"],
        integrity=original["integrity"],
        protocol_id=PROTOCOL_ID,
    )
    simple = dict(model="deepseek-flash", max_tokens=2048, thinking={"type": "disabled"})
    jobs = []
    for slot in SLOTS[:5719]:
        for role in ("A", "B"):
            eid = budget.review_episode_id(PROTOCOL_ID, slot["slot_id"], role)
            body = protocol.request_body(request) if eid == request["episode_id"] else simple
            jobs.append(
                dict(
                    episode_id=eid,
                    slot_id=slot["slot_id"],
                    task_id=slot["task_id"],
                    role=role,
                    max_output_tokens=body["max_tokens"],
                    request_sha256=digest(body),
                    request_body_sha256=hashlib.sha256(_json(body).encode()).hexdigest(),
                )
            )
    plan = budget.bound(
        dict(
            batch_id=budget.BATCH_ID,
            source_batch_id=budget.SOURCE_BATCH_ID,
            source_protocol_id="cpu-original-plan",
            source_root="/CPU-ONLY/source",
            model="deepseek-flash",
            concurrency=copy.deepcopy(CONCURRENCY),
            protocol_identity=PROTOCOL_ID,
            jobs=jobs,
        )
    )
    return plan, request


@pytest.fixture(scope="module")
def funded(tmp_path_factory, stopped_history):  # noqa: F811
    folder = tmp_path_factory.mktemp("v12-funded-fixture")
    ledger = clone(stopped_history, folder / "wallet.sqlite")
    register(ledger)
    fund(ledger, folder / "funding-backup.sqlite")
    return ledger.path


@pytest.fixture(scope="module")
def registered(tmp_path_factory, funded):
    folder = tmp_path_factory.mktemp("v12-registered-fixture")
    ledger = clone(funded, folder / "wallet.sqlite")
    plan, request = plan_and_request()
    permit = budget.register_matrix(
        ledger, plan, budget.authorization_definition(plan), backup_path=folder / "backup.sqlite"
    )
    return ledger.path, plan, request, permit


@pytest.fixture
def matrix(tmp_path, registered):
    path, plan, request, permit = registered
    return (
        clone(path, tmp_path / "wallet.sqlite"),
        copy.deepcopy(plan),
        copy.deepcopy(request),
        permit,
    )


def args(ledger, plan, index=1):
    job = plan["jobs"][index]
    body = dict(
        model="deepseek-flash", max_tokens=job["max_output_tokens"], thinking={"type": "disabled"}
    )
    coords = invocation_identity(
        dict(run_id=ledger.run_id, episode_id=job["episode_id"], attempt_index=1), turn_index=0
    )
    return dict(
        invocation_id=coords["invocation_id"],
        coordinates=coords,
        request=body,
        request_body=_json(body).encode(),
    )


def test_registration_backup_append_only_effective_caps_and_idempotence(funded, tmp_path):
    ledger = clone(funded, tmp_path / "wallet.sqlite")
    plan, _ = plan_and_request()
    before = {name: table(ledger.path, name) for name in ("counters", "v10_quotas", "metadata")}
    old = ledger.snapshot()
    backup = tmp_path / "before-v12.sqlite"
    permit = budget.register_matrix(
        ledger, plan, budget.authorization_definition(plan), backup_path=backup
    )
    assert all(table(backup, name) == rows for name, rows in before.items())
    assert all(table(ledger.path, name) == before[name] for name in ("counters", "v10_quotas"))
    assert dict(table(ledger.path, "metadata")) == {
        **dict(before["metadata"]),
        budget.KEY: _json(permit),
    }
    new = ledger.snapshot()
    assert new["exposure_microcny"] == old["exposure_microcny"]
    assert new["unknown_requests"] == new["acknowledged_unknown_requests"] == 65
    assert new["effective_hard_cap_microcny"] == 2_000_000_000
    effective = new["v10_partition"]["effective_limits"]
    assert effective == {
        "generation": {"requests": 191000, "microcny": 100_000_000},
        "review_mapping": {"requests": 25000, "microcny": 1_300_000_000},
    }
    assert new["v10_partition"]["unallocated_requests"] == 1924
    assert not new["v10_partition"]["original_950_buffer_spendable"]
    assert (
        budget.register_matrix(
            ledger, plan, budget.authorization_definition(plan), backup_path=backup
        )
        == permit
    )


def test_registration_rejects_changed_scope_and_rolls_back_publication(
    funded, tmp_path, monkeypatch
):
    ledger = clone(funded, tmp_path / "wallet.sqlite")
    plan, _ = plan_and_request()
    changed = copy.deepcopy(plan)
    changed["jobs"].pop()
    changed = budget.bound({k: v for k, v in changed.items() if k != "id"})
    with pytest.raises(RequestPartitionError):
        budget.register_matrix(
            ledger,
            changed,
            budget.authorization_definition(changed),
            backup_path=tmp_path / "no.sqlite",
        )
    assert not (tmp_path / "no.sqlite").exists()
    before = ledger.snapshot()
    original = ledger._event

    def fail(db, iid, action, value):
        original(db, iid, action, value)
        if action == budget.ACTION:
            raise RuntimeError("synthetic publication failure")

    monkeypatch.setattr(ledger, "_event", fail)
    with pytest.raises(RuntimeError):
        budget.register_matrix(
            ledger,
            plan,
            budget.authorization_definition(plan),
            backup_path=tmp_path / "retained.sqlite",
        )
    assert ledger.snapshot() == before and (tmp_path / "retained.sqlite").is_file()
    with sqlite3.connect(ledger.path) as db:
        assert not db.execute(
            "SELECT 1 FROM sqlite_master WHERE name='v12_review_roster'"
        ).fetchone()


def test_new_roster_bytes_no_old_queue_mapping_retry_and_exact_reserved_resume(matrix):
    ledger, plan, _, _ = matrix
    call = args(ledger, plan)
    for altered in (dict(call, request_body=call["request_body"] + b" "),):
        with pytest.raises(BudgetUnavailable, match="bytes"):
            ledger.reserve(**altered)
    for episode in (
        review_episode_id(budget.SOURCE_BATCH_ID, SLOTS[0]["slot_id"], "A"),
        "v12map:not-authorized",
    ):
        altered = copy.deepcopy(call)
        coords = invocation_identity(
            dict(run_id=ledger.run_id, episode_id=episode, attempt_index=1), turn_index=0
        )
        altered.update(invocation_id=coords["invocation_id"], coordinates=coords)
        with pytest.raises(BudgetUnavailable):
            ledger.reserve(**altered)
    altered = copy.deepcopy(call)
    coords = invocation_identity(
        dict(run_id=ledger.run_id, episode_id=call["coordinates"]["episode_id"], attempt_index=2),
        turn_index=0,
    )
    altered.update(invocation_id=coords["invocation_id"], coordinates=coords)
    with pytest.raises(BudgetUnavailable, match="retries"):
        ledger.reserve(**altered)
    ledger.reserve(**call)
    before = ledger.snapshot()
    budget.continue_reserved(ledger, **call)
    assert ledger.snapshot() == before
    ledger.mark_dispatched(call["invocation_id"])
    with pytest.raises(DuplicateInvocation):
        budget.continue_reserved(ledger, **call)


@pytest.mark.parametrize("edge", ["request", "money"])
def test_effective_caps_atomic_concurrent_reservations_without_editing_original_limits(
    matrix, edge
):
    ledger, plan, _, _ = matrix
    with sqlite3.connect(ledger.path) as db:
        if edge == "request":
            db.execute("UPDATE v10_quotas SET requests=24999 WHERE category='review_mapping'")
            db.execute("UPDATE counters SET requests=requests+24999")
        else:
            db.execute("UPDATE v10_quotas SET spent=1297500000 WHERE category='review_mapping'")
            db.execute("UPDATE counters SET spent=spent+1297500000")

    def one(i):
        try:
            ledger.reserve(**args(ledger, plan, i))
            return True
        except BudgetUnavailable:
            return False

    with ThreadPoolExecutor(max_workers=4) as workers:
        assert sum(workers.map(one, range(1, 5))) == 1
    state = ledger.snapshot()
    q = state["v10_partition"]["consumed"]["review_mapping"]
    assert q["requests"] <= 25000 and q["spent"] + q["held"] <= 1_300_000_000
    with sqlite3.connect(ledger.path) as db:
        assert db.execute(
            "SELECT request_cap,money_cap FROM v10_quotas WHERE category='review_mapping'"
        ).fetchone() == (17000, 550_000_000)


def mark_unknown(ledger, call, **extra):
    detail = dict(
        exception_type="ReadError",
        service_response_received=False,
        budget_invocation_id=call["invocation_id"],
        budget_coordinates=call["coordinates"],
        request_sha256=digest(call["request"]),
    )
    detail.update(extra)
    ledger.unknown(call["invocation_id"], reason=budget.NETWORK_REASON, evidence=detail)


def test_drained_network_group_preserves_all_three_holds_and_ack_recovery_without_retry(matrix):
    ledger, plan, _, _ = matrix
    calls = [args(ledger, plan, i) for i in (1, 2, 3)]
    for call in calls:
        ledger.reserve(**call)
        ledger.mark_dispatched(call["invocation_id"])
    mark_unknown(ledger, calls[0])
    expected = {c["invocation_id"]: digest(c["request"]) for c in calls}
    with pytest.raises(UnknownAbandonmentError, match="drain"):
        budget.acknowledge_connection_unknowns(
            ledger, protocol_id=PROTOCOL_ID, expected_requests=expected
        )
    for call in calls[1:]:
        mark_unknown(ledger, call)
    before = ledger.snapshot()
    receipt = budget.acknowledge_connection_unknowns(
        ledger, protocol_id=PROTOCOL_ID, expected_requests=expected
    )
    assert len(receipt["records"]) == receipt["drained_wave_unknown_count"] == 3
    after = ledger.snapshot()
    assert after["held_microcny"] == before["held_microcny"] and after["halt"] is None
    assert after["acknowledged_unknown_requests"] == 68
    assert all(
        r["model_response"] is None and not r["retry_authorized"] for r in receipt["records"]
    )
    assert (
        budget.acknowledge_connection_unknowns(
            ledger, protocol_id=PROTOCOL_ID, expected_requests=expected
        )
        == receipt
    )
    assert ledger.snapshot() == after


def test_once_provider_exact_settled_restore_malformed_original_and_no_repeat(matrix):
    ledger, _, request, _ = matrix
    client = Client(response_fixture('{"process":', finish="length"))
    artifact = asyncio.run(
        provider.request_once(ledger=ledger, api_key=KEY, request=request, client=client)
    )
    row = ledger.request_record(artifact["budget_invocation_id"])
    before = ledger.snapshot()
    assert provider.restore_settled(row, json.loads(_json(request))) == artifact
    record = provider.paid_record(request, artifact, row)
    assert record["schema"] == "v12_paid_process_review.v1"
    assert record["actual_model_call_receipt_verified"]
    assert not record["inspection"]["training_admissibility"]["production_admitted"]
    assert record["new_pipeline_outcomes"]["process_validity"] == "unknown"
    assert artifact["review_text"] == '{"process":'
    with pytest.raises(DuplicateInvocation):
        asyncio.run(
            provider.request_once(ledger=ledger, api_key=KEY, request=request, client=client)
        )
    assert len(client.calls) == 1 and ledger.snapshot() == before


def test_provider_reserved_continuation_and_wrong_request_never_send(matrix):
    ledger, _, request, _ = matrix
    body = protocol.request_body(request)
    coords = invocation_identity(
        dict(run_id=ledger.run_id, episode_id=request["episode_id"], attempt_index=1), turn_index=0
    )
    ledger.reserve(
        coords["invocation_id"], coordinates=coords, request=body, request_body=_json(body).encode()
    )
    before_count = ledger.snapshot()["requests_reserved"]
    client = Client(response_fixture())
    artifact = asyncio.run(
        provider.request_once(
            ledger=ledger, api_key=KEY, request=request, client=client, resume_reserved=True
        )
    )
    assert artifact["actual_model_calls"] == 1 and len(client.calls) == 1
    assert ledger.snapshot()["requests_reserved"] == before_count
    changed = copy.deepcopy(request)
    changed["model"] = "not-flash"
    with pytest.raises(ValueError):
        asyncio.run(
            provider.request_once(ledger=ledger, api_key=KEY, request=changed, client=client)
        )
    assert len(client.calls) == 1


@pytest.mark.parametrize("network", [True, False])
def test_provider_unknown_hold_network_only_ack_and_never_resend(matrix, network):
    ledger, _, request, _ = matrix
    client = (
        Client(failure=httpx.ReadError("synthetic connection loss"))
        if network
        else Client({"error": "quota"}, status=429)
    )
    with pytest.raises(ProviderCallError):
        asyncio.run(
            provider.request_once(ledger=ledger, api_key=KEY, request=request, client=client)
        )
    coords = invocation_identity(
        dict(run_id=ledger.run_id, episode_id=request["episode_id"], attempt_index=1), turn_index=0
    )
    row = ledger.request_record(coords["invocation_id"])
    assert row["state"] == "UNKNOWN" and row["usage_json"] is None
    held = ledger.snapshot()["held_microcny"]
    kwargs = dict(
        protocol_id=PROTOCOL_ID, expected_requests={coords["invocation_id"]: row["request_sha256"]}
    )
    if network:
        budget.acknowledge_connection_unknowns(ledger, **kwargs)
        assert ledger.snapshot()["halt"] is None
    else:
        with pytest.raises(UnknownAbandonmentError):
            budget.acknowledge_connection_unknowns(ledger, **kwargs)
        assert ledger.snapshot()["halt"]
    assert ledger.snapshot()["held_microcny"] == held
    with pytest.raises(DuplicateInvocation):
        asyncio.run(
            provider.request_once(
                ledger=ledger, api_key=KEY, request=request, client=client, resume_reserved=True
            )
        )
    assert len(client.calls) == 1


def test_explicit_proxy_verified_tls_zero_retry_64_pool_1200_timeout(monkeypatch):
    monkeypatch.setenv("HTTPS_PROXY", "http://127.0.0.1:9999")
    client = provider.annotation_client(proxy="http://127.0.0.1:7897")
    pool = client._transport._pool
    assert not client._trust_env and pool._retries == 0
    assert pool._max_connections == pool._max_keepalive_connections == 64
    assert pool._proxy_url.port == 7897 and pool._ssl_context.check_hostname
    assert client.timeout.read == 1200 and client.timeout.connect == 30
    asyncio.run(client.aclose())
