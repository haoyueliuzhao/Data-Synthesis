"""CPU-only controls; mocked HTTP is never published as authentic Probe data."""

import copy
import json
import sqlite3
from concurrent.futures import ThreadPoolExecutor
from types import SimpleNamespace

import pytest
from test_qa_vnext_catalog_bridge_worker import fixture

from trusted_synthesis.experiments.finance_qa_vnext_catalog_bridge.controls import (
    script_for_witness,
)
from trusted_synthesis.experiments.finance_qa_vnext_eval_readiness import training_runtime as old
from trusted_synthesis.experiments.finance_qa_vnext_eval_readiness.transport import (
    render as old_render,
)
from trusted_synthesis.experiments.finance_qa_vnext_probe_coverage import (
    assessment,
    budget,
    runtime,
    transport,
)
from trusted_synthesis.experiments.finance_qa_vnext_probe_coverage import (
    protocol as p,
)


def tasks():
    result = []
    for family in p.FAMILIES:
        for quantity in p.QUANTITIES:
            for i in range(2):
                task_id = f"{family}:{quantity}:{i}"
                result.append(
                    dict(
                        task_id=task_id,
                        family=family,
                        quantity=quantity,
                        source_cluster=f"cik:{family}:{i}",
                        bundle_id="bundle:" + task_id,
                        bundle_path="parent/bundle",
                        public_path="parent/public",
                        public_messages_sha256="a" * 64,
                        surface_version_id="surface:" + task_id,
                        parent_manifest_id="parent",
                        parent_directory="parent",
                        native_bindings_path="parent/native_bindings.json",
                        scale_group=family,
                    )
                )
    return result


def registered(f, profile="P0_original", basis="endpoint", identifier="mock"):
    return dict(
        session_id=identifier,
        ordinal=0,
        task_id=f["identity"]["task_id"],
        family=f["identity"]["family"],
        quantity=f["bundle"]["private"]["canonical_target"]["quantity"],
        profile=profile,
        basis=basis,
        replicate=0,
        identity=copy.deepcopy(f["identity"]),
        system_prompt_sha256=p.sha(p.system_prompt(profile, basis)),
    )


def wallet(tmp_path, *, prior=0, fixture_value=None):
    path = tmp_path / "wallet.sqlite3"
    with sqlite3.connect(path) as db:
        db.execute("CREATE TABLE metadata(key TEXT PRIMARY KEY,value TEXT NOT NULL)")
        db.execute(
            "INSERT INTO metadata VALUES('policy',?)",
            (json.dumps({"stage_id": p.OWNER, "common_new_experiment_cap": p.COMMON_CAP}),),
        )
        db.execute("INSERT INTO metadata VALUES('old_marker','unchanged')")
        db.execute("CREATE TABLE prior_debits(name TEXT PRIMARY KEY,tokens INTEGER NOT NULL)")
        db.execute("INSERT INTO prior_debits VALUES('prior',?)", (prior,))
        for name in budget.OLD_RESERVATIONS:
            db.execute(f"""CREATE TABLE {name}(request_id TEXT PRIMARY KEY,state TEXT NOT NULL,
              reserved_tokens INTEGER NOT NULL,charged_tokens INTEGER NOT NULL,attempt INTEGER,
              created_at TEXT,prompt_tokens INTEGER,completion_tokens INTEGER,
              http_success INTEGER,response_model TEXT,outcome TEXT)""")
    selected = tasks()
    if fixture_value:
        selected[0].update(fixture_value["identity"])
    rows = p.make_registry(selected, "frozen_test")
    ledger = budget.CoverageLedger(path, "frozen_test")
    with ledger.connection(readonly=True) as db:
        before = budget.legacy_snapshot(db)
    ledger.register(rows, selected, legacy_before=before)
    return ledger, rows, selected, before


def settle_ok(ledger, sid, amount=3):
    lease = ledger.reserve(sid)
    ledger.mark_sent(lease["request_id"])
    ledger.settle(
        lease["request_id"],
        usage={"prompt_tokens": amount, "completion_tokens": 0, "total_tokens": amount},
        http_success=True,
        response_model=p.MODEL,
        outcome="public_response_received",
    )
    return lease


def test_policy_bounds_no_training():
    assert p.checked(p.policy(), "coverage_policy") == p.policy()
    assert p.SESSION_CAP == 12 * 3 * 2 * 2 == 144 and p.REQUEST_CAP == 4608
    assert p.TOKEN_CAP == 40000000 and p.REQUEST_RESERVATION == 115712
    assert (
        not p.policy()["training_eligible"] and not p.policy()["creates_original_AB_material_pool"]
    )


@pytest.mark.parametrize("basis", p.BASES)
def test_baseline_exact_old_public_prompt_and_wire_body(basis):
    system = old.SYSTEM + "\n" + old.GUIDANCE[basis]
    assert p.system_prompt("P0_original", basis) == system
    messages = [{"role": "system", "content": system}, {"role": "user", "content": "json"}]
    assert transport.render(messages) == old_render(messages)


def test_selection_does_not_use_success_and_matrix_types_are_fixed():
    value = {
        "tasks": tasks()
        + [
            {"task_id": "control_" + str(i), "family": "control", "quantity": "difference"}
            for i in range(243)
        ]
    }
    chosen = p.select_tasks(value)
    for x in value["tasks"]:
        x.update(financial_valid=False, actual_method="UNDETERMINED")
    assert p.select_tasks(value) == chosen
    rows = p.make_registry(chosen, "f")
    p.validate_registry(rows, chosen, "f")
    assert len({x["session_id"] for x in rows}) == 144
    wrong = copy.deepcopy(rows)
    wrong[0]["ordinal"] = False
    with pytest.raises(ValueError):
        p.validate_registry(wrong, chosen, "f")
    with pytest.raises(ValueError):
        p.validate_registry(list(reversed(rows)), chosen, "f")


@pytest.mark.parametrize("profile", p.PROFILES)
@pytest.mark.parametrize("basis", p.BASES)
@pytest.mark.parametrize("actual", p.BASES)
@pytest.mark.parametrize("quantity", p.QUANTITIES)
def test_method_is_not_requested_guidance_or_profile(profile, basis, actual, quantity):
    f = fixture("annual_flow", quantity)
    reg = registered(f, profile, basis)
    queue = iter(script_for_witness(f["bundle"], f["native_bindings"], actual))
    session = runtime.generate(
        f["messages"],
        f["identity"],
        registered=reg,
        provider=lambda *_: p.encode(next(queue)).decode(),
    )
    assert runtime.replay(session) == session
    q = assessment.assess(
        session, f, {"session_id": session["id"], "status": "ORIGIN_NOT_VERIFIED_TEST_ONLY"}
    )
    assert q["financial_valid"] and q["actual_method"] == actual
    assert not q["token_diagnostic_eligible"] and not q["training_eligible"]


def test_baseline_tool_feedback_and_first_Final_rules_unchanged():
    f = fixture()
    script = ["bad JSON", {"tool": "calculate", "arguments": {}}] + script_for_witness(
        f["bundle"], f["native_bindings"]
    )

    def callback(queue):
        return lambda *_: x if isinstance(x := next(queue), str) else p.encode(x).decode()

    a = old.generate(
        f["messages"],
        f["identity"],
        provider=callback(iter(script)),
        session_id="mock",
        requested_basis="endpoint",
    )
    b = runtime.generate(
        f["messages"], f["identity"], provider=callback(iter(script)), registered=registered(f)
    )
    assert a["events"] == b["events"] and a["initial_messages"] == b["initial_messages"]
    assert [x["input_messages"] for x in a["turns"]] == [x["input_messages"] for x in b["turns"]]
    c = runtime.generate(
        f["messages"],
        f["identity"],
        provider=lambda *_: '{"final":"bad"}',
        registered=registered(f),
    )
    assert c["provider_calls"] == 1 and runtime.replay(c) == c


def test_fatal_replay_and_parallel_profiles_do_not_patch_legacy():
    f = fixture()
    before = old.SYSTEM

    def fail(*_):
        raise transport.FatalProbeError("test_only")

    failed = runtime.generate(f["messages"], f["identity"], registered=registered(f), provider=fail)
    assert failed["global_fatal"] and runtime.replay(failed) == failed

    def one(profile):
        return runtime.generate(
            f["messages"],
            f["identity"],
            registered=registered(f, profile),
            provider=lambda *_: '{"final":"bad"}',
        )

    with ThreadPoolExecutor(max_workers=3) as pool:
        values = list(pool.map(one, p.PROFILES))
    assert old.SYSTEM == before and len({x["initial_messages"][0]["content"] for x in values}) == 3


def test_old_wallet_logical_rows_unchanged_and_registration_once(tmp_path):
    ledger, rows, selected, before = wallet(tmp_path, prior=221538)
    with ledger.connection(readonly=True) as db:
        assert budget.legacy_snapshot(db, before) == before
    assert ledger.snapshot()["common_conservative_debit"] == 221538
    with pytest.raises(budget.BudgetStop):
        ledger.register(rows, selected, legacy_before=before)
    assert len(ledger.sessions()) == 144


def test_same_session_reservation_and_send_are_atomic(tmp_path):
    ledger, rows, _, _ = wallet(tmp_path)
    sid = rows[0]["session_id"]

    def one(_):
        try:
            return ledger.reserve(sid)
        except budget.BudgetStop:
            return None

    with ThreadPoolExecutor(max_workers=4) as pool:
        values = list(pool.map(one, range(4)))
    assert sum(x is not None for x in values) == 1
    lease = next(x for x in values if x)
    ledger.mark_sent(lease["request_id"])
    with pytest.raises(budget.BudgetStop):
        ledger.mark_sent(lease["request_id"])


@pytest.mark.parametrize(
    "usage",
    [
        None,
        {},
        {"prompt_tokens": True, "completion_tokens": 1, "total_tokens": 2},
        {"prompt_tokens": 2, "completion_tokens": 1, "total_tokens": 99},
    ],
)
def test_unknown_cost_held_and_failed_session_not_retried(tmp_path, usage):
    ledger, rows, _, _ = wallet(tmp_path)
    sid = rows[0]["session_id"]
    lease = ledger.reserve(sid)
    ledger.mark_sent(lease["request_id"])
    assert not ledger.settle(lease["request_id"], usage=usage, outcome="network")
    assert ledger.requests(sid)[0]["charged_tokens"] == p.REQUEST_RESERVATION
    with pytest.raises(budget.BudgetStop):
        ledger.reserve(sid)
    assert ledger.reserve(rows[1]["session_id"])


@pytest.mark.parametrize("table", budget.OLD_RESERVATIONS)
def test_old_purpose_sees_probe_debit(tmp_path, table):
    ledger, rows, _, _ = wallet(tmp_path, prior=p.COMMON_CAP - p.REQUEST_RESERVATION)
    ledger.reserve(rows[0]["session_id"])
    with ledger.connection() as db, pytest.raises(sqlite3.IntegrityError, match="four_purpose_cap"):
        db.execute(
            f"INSERT INTO {table}(request_id,state,reserved_tokens,charged_tokens) "
            "VALUES('old','reserved',1,1)"
        )


def test_probe_subcap_and_known_unused_release(tmp_path, monkeypatch):
    monkeypatch.setattr(p, "TOKEN_CAP", p.REQUEST_RESERVATION)
    ledger, rows, _, _ = wallet(tmp_path)
    lease = settle_ok(ledger, rows[0]["session_id"], 77)
    assert ledger.snapshot()["probe_conservative_debit"] == 77
    with pytest.raises(budget.BudgetStop, match="subcap"):
        ledger.reserve(rows[1]["session_id"])
    with pytest.raises(budget.BudgetStop):
        ledger.settle(lease["request_id"], outcome="second")


def test_HTTP200_unknown_halts_common_but_inflight_can_settle(tmp_path):
    ledger, rows, _, _ = wallet(tmp_path)
    a, b = [ledger.reserve(row["session_id"]) for row in rows[:2]]
    for x in (a, b):
        ledger.mark_sent(x["request_id"])
    ledger.settle(a["request_id"], http_success=True, response_model=p.MODEL, outcome="unknown")
    with pytest.raises(budget.BudgetStop):
        ledger.reserve(rows[2]["session_id"])
    ledger.settle(
        b["request_id"],
        usage={"prompt_tokens": 2, "completion_tokens": 1, "total_tokens": 3},
        http_success=True,
        response_model=p.MODEL,
        outcome="public_response_received",
    )
    assert "study_fatal" in ledger.snapshot()["persisted_stops"]
    assert ledger.requests(rows[1]["session_id"])[0]["charged_tokens"] == 3


@pytest.mark.parametrize("field", ["prompt_tokens", "completion_tokens"])
def test_breach_not_refunded_and_global_stop(tmp_path, field):
    ledger, rows, _, _ = wallet(tmp_path)
    x = ledger.reserve(rows[0]["session_id"])
    ledger.mark_sent(x["request_id"])
    usage = {"prompt_tokens": 1, "completion_tokens": 1}
    usage[field] = (p.INPUT_ALLOWANCE if field == "prompt_tokens" else p.OUTPUT_ALLOWANCE) + 1
    usage["total_tokens"] = usage["prompt_tokens"] + usage["completion_tokens"]
    assert not ledger.settle(
        x["request_id"], usage=usage, http_success=True, response_model=p.MODEL, outcome="breach"
    )
    assert ledger.requests()[0]["charged_tokens"] == usage["total_tokens"]
    with pytest.raises(budget.BudgetStop):
        ledger.reserve(rows[1]["session_id"])


def test_frozen_registry_and_request_history_cannot_be_rewritten(tmp_path):
    ledger, rows, _, _ = wallet(tmp_path)
    settle_ok(ledger, rows[0]["session_id"])
    with ledger.connection() as db:
        for sql in [
            "DELETE FROM probe01_requests",
            "DELETE FROM probe01_sessions",
            "UPDATE probe01_sessions SET basis='movement'",
            "UPDATE probe01_requests SET charged_tokens=0",
        ]:
            with pytest.raises(sqlite3.IntegrityError):
                db.execute(sql)
    ledger.finish(rows[0]["session_id"], "first_final")
    with pytest.raises(budget.BudgetStop):
        ledger.reserve(rows[0]["session_id"])


class FakeSender:
    def __init__(self, script, *, content=None, status=200):
        self.script = iter(script)
        self.content = content
        self.status = status
        self.calls = []

    def send(self, payload, *, api_key):
        self.calls.append(payload)
        raw = self.content if self.content is not None else p.encode(next(self.script)).decode()
        return SimpleNamespace(
            complete=True,
            status_code=self.status,
            body=p.encode(
                {
                    "model": p.MODEL,
                    "choices": [
                        {
                            "message": {
                                "content": raw,
                                "reasoning_content": "PRIVATE_REASONING_TEST_CANARY",
                            },
                            "finish_reason": "stop",
                        }
                    ],
                    "usage": {"prompt_tokens": 2, "completion_tokens": 1, "total_tokens": 3},
                }
            ),
        )


def provider_setup(tmp_path, *, content=None, status=200, monkeypatch=None):
    f = fixture()
    ledger, rows, _, _ = wallet(tmp_path, fixture_value=f)
    reg = next(x for x in rows if x["task_id"] == f["identity"]["task_id"])
    sender = FakeSender(
        script_for_witness(f["bundle"], f["native_bindings"]), content=content, status=status
    )
    if monkeypatch:
        monkeypatch.setattr(transport, "HttpxSender", lambda config: sender)
    provider = transport.Provider(
        ledger,
        reg,
        tmp_path / "requests",
        "TEST_ONLY_CREDENTIAL",
        sender=None if monkeypatch else sender,
    )
    session = runtime.generate(f["messages"], f["identity"], registered=reg, provider=provider)
    return f, ledger, reg, sender, session


def test_mock_callback_is_not_authentic_and_private_reasoning_not_saved(tmp_path):
    _, ledger, reg, sender, session = provider_setup(tmp_path)
    assert runtime.replay(session) == session and session["terminal"] == "first_final"
    with pytest.raises(ValueError, match="authentic_exact_request_response_chain"):
        transport.verify_origin(session, ledger, tmp_path / "requests")
    assert all(
        b"PRIVATE_REASONING_TEST_CANARY" not in x.read_bytes()
        for x in (tmp_path / "requests").rglob("*.json")
    )
    assert ledger.snapshot()["probe_conservative_debit"] == 3 * len(sender.calls)


def test_origin_verifier_mocked_HTTP_constructor_unit_boundary(tmp_path, monkeypatch):
    _, ledger, reg, sender, session = provider_setup(tmp_path, monkeypatch=monkeypatch)
    result = transport.verify_origin(session, ledger, tmp_path / "requests")
    assert result["complete_first_Final_request_chain"] and len(sender.calls) == len(
        session["turns"]
    )
    # The trusted sender is monkeypatched ONLY in this test; this is not a real Probe.
    one = next((tmp_path / "requests").rglob("receipt.json"))
    value = json.loads(one.read_bytes())
    value["known_usage"] = False
    with pytest.raises(ValueError):
        p.checked(value, "probe_request_receipt")


@pytest.mark.parametrize("status", [400, 401, 402, 403])
def test_fixed_request_auth_billing_error_stops_batch(tmp_path, status):
    _, ledger, reg, sender, session = provider_setup(tmp_path, status=status)
    assert session["global_fatal"] and len(sender.calls) == 1
    assert ledger.requests(reg["session_id"])[0]["charged_tokens"] == p.REQUEST_RESERVATION


def test_empty_content_keeps_known_charge_without_retry(tmp_path):
    _, ledger, reg, sender, session = provider_setup(tmp_path, content="")
    assert not session["global_fatal"] and session["terminal"] == "transport_session_terminal"
    assert len(sender.calls) == 1 and ledger.requests(reg["session_id"])[0]["charged_tokens"] == 3
    value = json.loads(next((tmp_path / "requests").rglob("public_response.json")).read_bytes())
    assert (
        value["original_public_content_is_string"] and not value["original_public_content_nonempty"]
    )


def test_incomplete_registry_never_constructs_tokenizer():
    def forbidden(*_):
        raise AssertionError("no tokenizer")

    result = assessment.token_diagnostics([], None, complete_registry=False, loader=forbidden)
    assert result["tokenizer_loads"] == 0
