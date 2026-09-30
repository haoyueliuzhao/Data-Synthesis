"""Bounded V13 temporary-wallet/mock controls; no paid, GPU or real-wallet operations."""

import asyncio
import copy
import hashlib
import json
import sqlite3
from types import SimpleNamespace

import httpx
import pytest
from test_finance_research_probe_provider import Client
from test_finance_unknown_abandonment import table
from test_finance_v6_strict_review_provider import response_fixture
from test_finance_v10_budget import SLOTS, stopped_history, synthetic_parent  # noqa: F401
from test_finance_v10_process_review import fixture as original_fixture
from test_finance_v12_budget_provider import clone, funded, registered  # noqa: F401
from test_finance_v12_review_controller import MemoryBudget, MemoryLedger, MemoryProvider
from test_finance_v13_material_protocol import bindings

from trusted_synthesis.finance_research import v11_process_review as original
from trusted_synthesis.finance_research import v13_budget as budget
from trusted_synthesis.finance_research import v13_material_controller as ctl
from trusted_synthesis.finance_research import v13_material_protocol as protocol
from trusted_synthesis.finance_research import v13_material_provider as provider
from trusted_synthesis.finance_research.contracts import (
    ProviderCallError,
    digest,
    invocation_identity,
)
from trusted_synthesis.finance_research.probe_budget import (
    BudgetUnavailable,
    DuplicateInvocation,
    UnknownAbandonmentError,
)
from trusted_synthesis.finance_research.providers import _json

PROTOCOL = "synthetic-v13-material-only"
KEY = "not-a-real-API-key-CPU"


@pytest.fixture(scope="module")
def v13_seed(tmp_path_factory, registered):  # noqa: F811
    parent_path, parent_plan, _, _ = registered
    folder = tmp_path_factory.mktemp("v13-synthetic-scope")
    ledger = clone(parent_path, folder / "wallet.sqlite")
    groups = {}
    for task in range(744):
        count = 4 if task < 434 else 3 if task < 645 else 1
        groups[SLOTS[task * 8]["task_id"]] = [SLOTS[task * 8 + j]["slot_id"] for j in range(count)]
    common = [sid for slots in groups.values() for sid in slots]
    blocked = common[:671]
    seal = budget.bound(
        dict(
            schema="synthetic_V12_seal_not_paid",
            joint_process_candidate_slot_ids=common,
            projection_blocked_candidate_slot_ids=blocked,
        )
    )
    source = folder / "synthetic-source"
    (source / "review_seal").mkdir(parents=True)
    (source / "review_seal/record.json").write_text(_json(seal))
    mp = pytest.MonkeyPatch()
    mp.setattr(budget, "SOURCE_SEAL_ID", seal["id"])
    views = []
    episode, old, _ = original_fixture()
    episode = episode.model_copy(update={"task_id": SLOTS[0]["task_id"]})
    for sid in groups[episode.task_id]:
        views.append(
            original.prepare_review_request(
                episode,
                slot_id=sid,
                role="A",
                native_result=old["native_result"],
                integrity=old["integrity"],
            )["trajectory"]
        )
    requests = [
        protocol.prepare_projection(
            views[0], protocol_id=PROTOCOL, source_bindings=bindings([views[0]])
        ),
        protocol.prepare_mapping(views, protocol_id=PROTOCOL, source_bindings=bindings(views)),
    ]
    actual = {r["episode_id"]: r for r in requests}
    jobs = []
    for purpose in ("projection", "mapping"):
        for task, slots in groups.items():
            selected = (
                [[sid] for sid in slots if sid in blocked]
                if purpose == "projection"
                else ([slots] if len(slots) > 1 else [])
            )
            for cohort in selected:
                eid = budget.material_episode_id(PROTOCOL, purpose, task, cohort)
                body = (
                    protocol.request_body(actual[eid])
                    if eid in actual
                    else dict(
                        model="deepseek-flash", max_tokens=8192, thinking={"type": "disabled"}
                    )
                )
                jobs.append(
                    dict(
                        kind=purpose,
                        role=purpose,
                        purpose=purpose,
                        task_id=task,
                        slot_id=cohort[0] if purpose == "projection" else None,
                        slot_ids=cohort,
                        episode_id=eid,
                        max_output_tokens=body["max_tokens"],
                        request_sha256=digest(body),
                        request_body_sha256=hashlib.sha256(_json(body).encode()).hexdigest(),
                    )
                )
    plan = budget.bound(
        dict(
            schema="v13_fixed_candidate_material_plan.v1",
            batch_id=budget.BATCH_ID,
            source_batch_id=budget.SOURCE_BATCH_ID,
            source_root=str(source),
            source_protocol_id=parent_plan["id"],
            source_review_seal_id=seal["id"],
            fixed_task_slots=groups,
            jobs=jobs,
            model="deepseek-flash",
            protocol_identity=PROTOCOL,
            concurrency={"max": 64, "ramp": [{"settled_at_least": 0, "workers": 16}]},
        )
    )
    yield ledger.path, plan, requests, source
    mp.undo()


@pytest.fixture
def matrix(tmp_path, v13_seed):
    path, plan, requests, _ = v13_seed
    ledger = clone(path, tmp_path / "wallet.sqlite")
    before = ledger.snapshot()
    permit = budget.register_matrix(
        ledger, plan, budget.authorization_definition(plan), backup_path=tmp_path / "backup.sqlite"
    )
    return ledger, copy.deepcopy(plan), copy.deepcopy(requests), permit, before


def response(text="{}", *, tool="submit_material"):
    value = response_fixture(text)
    value["choices"][0]["message"]["tool_calls"][0]["function"]["name"] = tool
    return value


def reserve_args(ledger, request):
    body = protocol.request_body(request)
    coords = invocation_identity(
        dict(run_id=ledger.run_id, episode_id=request["episode_id"], attempt_index=1), turn_index=0
    )
    return dict(
        invocation_id=coords["invocation_id"],
        coordinates=coords,
        request=body,
        request_body=_json(body).encode(),
    )


def test_new_exact_scope_append_preserves_parent_rows_and_quotas(matrix):
    ledger, plan, _, permit, before = matrix
    assert len(plan["jobs"]) == 1316 and permit["purpose_counts"] == {
        "projection": 671,
        "mapping": 645,
    }
    assert ledger.snapshot() == before
    for name in ("requests", "counters", "v10_quotas"):
        assert table(ledger.path, name) == table(permit["backup"]["path"], name)
    with sqlite3.connect(ledger.path) as db:
        assert db.execute("SELECT COUNT(*) FROM v12_review_roster").fetchone()[0] == 11438
        assert db.execute("SELECT COUNT(*) FROM v13_review_roster").fetchone()[0] == 1316
    assert (
        budget.register_matrix(
            ledger,
            plan,
            budget.authorization_definition(plan),
            backup_path=permit["backup"]["path"],
        )
        == permit
    )


def test_wrong_source_scope_and_partial_multi_rejected_before_backup(tmp_path, v13_seed):
    path, plan, _, _ = v13_seed
    ledger = clone(path, tmp_path / "wallet.sqlite")
    bad = copy.deepcopy(plan)
    mapping = next(j for j in bad["jobs"] if j["kind"] == "mapping")
    mapping["slot_ids"] = mapping["slot_ids"][:2]
    bad = budget.bound({k: v for k, v in bad.items() if k != "id"})
    with pytest.raises(ValueError, match="whole multi"):
        budget.register_matrix(
            ledger,
            bad,
            budget.authorization_definition(bad),
            backup_path=tmp_path / "absent.sqlite",
        )
    assert not (tmp_path / "absent.sqlite").exists()


def test_provider_new_tool_real_temporary_settlement_both_purposes_and_restore(matrix):
    ledger, _, requests, _, _ = matrix
    for request in requests:
        client = Client(response('{"bad":true}'))
        artifact = asyncio.run(
            provider.request_once(ledger=ledger, api_key=KEY, request=request, client=client)
        )
        row = ledger.request_record(artifact["budget_invocation_id"])
        assert artifact["review_text"] == '{"bad":true}'
        assert provider.restore_settled(row, json.loads(_json(request))) == artifact
        record = provider.paid_record(request, artifact, row)
        assert record["schema"] == "v13_paid_material_annotation.v1"
        assert (
            record["actual_model_call_receipt_verified"]
            and not record["inspection"]["production_admitted"]
        )
        assert not record["inspection"].get("usable", record["inspection"].get("mapping_admitted"))
        with pytest.raises(DuplicateInvocation):
            asyncio.run(
                provider.request_once(ledger=ledger, api_key=KEY, request=request, client=client)
            )
        assert len(client.calls) == 1


def test_wrong_tool_is_paid_failure_not_exception_and_no_automatic_resend(matrix):
    ledger, _, requests, _, _ = matrix
    client = Client(response(tool="submit_review"))
    artifact = asyncio.run(
        provider.request_once(ledger=ledger, api_key=KEY, request=requests[0], client=client)
    )
    record = provider.paid_record(
        requests[0], artifact, ledger.request_record(artifact["budget_invocation_id"])
    )
    assert artifact["review_text"] is None and artifact["review_format_error"]
    assert record["inspection"]["raw_review"] is None and not record["inspection"]["usable"]


def test_exact_reserved_resume_rejects_old_namespace_and_attempt2(matrix):
    ledger, _, requests, _, _ = matrix
    call = reserve_args(ledger, requests[0])
    for eid, attempt in (("v12review:" + "1" * 64, 1), (requests[0]["episode_id"], 2)):
        coords = invocation_identity(
            dict(run_id=ledger.run_id, episode_id=eid, attempt_index=attempt), turn_index=0
        )
        with pytest.raises(BudgetUnavailable):
            ledger.reserve(
                coords["invocation_id"],
                coordinates=coords,
                request=call["request"],
                request_body=call["request_body"],
            )
    ledger.reserve(**call)
    count = ledger.snapshot()["requests_reserved"]
    artifact = asyncio.run(
        provider.request_once(
            ledger=ledger,
            api_key=KEY,
            request=requests[0],
            client=Client(response()),
            resume_reserved=True,
        )
    )
    assert ledger.snapshot()["requests_reserved"] == count and artifact["actual_model_calls"] == 1


@pytest.mark.parametrize("network", [True, False])
def test_network_only_terminal_preserves_hold_no_service_halt_bypass(matrix, network):
    ledger, _, requests, _, _ = matrix
    request = requests[0]
    client = (
        Client(failure=httpx.ReadError("CPU network loss"))
        if network
        else Client({"error": "limited"}, status=429)
    )
    with pytest.raises(ProviderCallError):
        asyncio.run(
            provider.request_once(ledger=ledger, api_key=KEY, request=request, client=client)
        )
    iid = reserve_args(ledger, request)["invocation_id"]
    row = ledger.request_record(iid)
    before = ledger.snapshot()
    kwargs = dict(protocol_id=PROTOCOL, expected_requests={iid: row["request_sha256"]})
    if network:
        receipt = budget.acknowledge_connection_unknowns(ledger, **kwargs)
        assert receipt["records"][0]["model_response"] is None
        assert ledger.snapshot()["halt"] is None
    else:
        with pytest.raises(UnknownAbandonmentError):
            budget.acknowledge_connection_unknowns(ledger, **kwargs)
        assert ledger.snapshot()["halt"]
    assert ledger.snapshot()["held_microcny"] == before["held_microcny"]
    with pytest.raises(DuplicateInvocation):
        asyncio.run(
            provider.request_once(
                ledger=ledger, api_key=KEY, request=request, client=client, resume_reserved=True
            )
        )
    assert len(client.calls) == 1


class MaterialMemoryProvider(MemoryProvider):
    def paid_record(self, request, artifact, row):
        assert row["state"] == "SETTLED"
        kind = request["role"]
        inspection = dict(actual_model_call_receipt_verified=False, production_admitted=False)
        inspection.update(
            usable=False if kind == "projection" else None,
            mapping_status="complete" if kind == "mapping" else None,
            mapping_admitted=kind == "mapping",
        )
        return ctl.bound(
            dict(
                schema="v13_paid_material_annotation.v1",
                request=request,
                artifact=artifact,
                inspection=inspection,
                actual_model_call_receipt_verified=True,
                role=kind,
                purpose=kind,
                slot_id=request["slot_id"],
                slot_ids=request["slot_ids"],
                task_id=request["task_id"],
                protocol_id=PROTOCOL,
            )
        )


def memory_context(tmp_path, monkeypatch, counts=None, capacity=64):
    counts = counts or ctl.PURPOSE_COUNTS
    provider = MaterialMemoryProvider()
    monkeypatch.setattr(ctl, "_provider", lambda: provider)
    monkeypatch.setattr(ctl, "_budget", lambda: MemoryBudget)
    monkeypatch.setattr(ctl, "_protocol", lambda: SimpleNamespace(request_body=lambda r: r))
    monkeypatch.setattr(ctl, "explicit_proxy", lambda plan: "http://127.0.0.1:7897")
    jobs, requests = [], {}
    for index in range(max(counts.values())):
        for purpose, count in counts.items():
            if index >= count:
                continue
            slots = [
                "v10gen:" + digest([index, k]) for k in range(1 if purpose == "projection" else 2)
            ]
            eid = budget.material_episode_id(PROTOCOL, purpose, f"task-{index}", slots)
            request = ctl.bound(
                dict(
                    episode_id=eid,
                    role=purpose,
                    purpose=purpose,
                    slot_id=slots[0] if purpose == "projection" else None,
                    slot_ids=slots,
                    task_id=f"task-{index}",
                    max_output_tokens=8192,
                )
            )
            requests[eid] = request
            jobs.append(
                dict(
                    kind=purpose,
                    **{
                        k: request[k]
                        for k in (
                            "episode_id",
                            "role",
                            "slot_id",
                            "slot_ids",
                            "task_id",
                            "max_output_tokens",
                        )
                    },
                    request_id=request["id"],
                    request_sha256=digest(request),
                    request_body_sha256=ctl.sha(ctl.canonical(request)),
                )
            )
    ctx = SimpleNamespace(
        output=tmp_path,
        jobs=jobs,
        progress={},
        plan=dict(
            id="synthetic-V13-plan",
            protocol_identity=PROTOCOL,
            source_review_seal_id="synthetic-not-production",
            concurrency={
                "max": 64,
                "ramp": [
                    {"settled_at_least": 0, "workers": 16},
                    {"settled_at_least": 16, "workers": 32},
                    {"settled_at_least": 64, "workers": 64},
                ],
            },
        ),
    )
    ctx.update = lambda **values: ctx.progress.update(values)
    ctx.request = lambda job: requests[job["episode_id"]]
    return ctx, MemoryLedger(capacity), provider


def test_controller_full1316_independent_mapping_and_unusable_projection_kept(
    tmp_path, monkeypatch
):
    ctx, ledger, mock = memory_context(tmp_path, monkeypatch)
    complete = asyncio.run(ctl.execute_material(ctx, ledger, api_key=KEY))
    assert len(complete) == len(mock.calls) == 1316 and mock.maximum == 64
    assert ctx.progress["successful_transport_settlements"] == 1316
    with pytest.raises(ValueError, match="partial"):
        ctl.freeze_completion_seal(ctx, dict(list(complete.items())[:-1]))
    seal = ctl.freeze_completion_seal(ctx, complete)
    assert seal["projection_usable_calls"] == 0 and seal["mapping_complete_calls"] == 645
    assert seal["actual_returns"] == 1316 and not seal["production_admitted"]
    assert len(seal["terminals"]) == 1316
    again = asyncio.run(ctl.execute_material(ctx, ledger, api_key=KEY))
    assert again == complete and len(mock.calls) == 1316


def test_controller_network_wave_saves_and_budget_zero_never_dispatches(tmp_path, monkeypatch):
    ctx, ledger, mock = memory_context(tmp_path, monkeypatch, {"projection": 6, "mapping": 6})
    mock.failures.update({job["episode_id"]: "network" for job in ctx.jobs[:3]})
    assert asyncio.run(ctl.execute_material(ctx, ledger, api_key=KEY)) is None
    assert (
        ctx.progress["phase"] == "NETWORK_SAFETY_SAVED"
        and ledger.snapshot()["pending_requests"] == 0
    )
    assert len(ledger.acks) == 3 and len(mock.calls) == 12
    other, empty, no_call = memory_context(
        tmp_path / "budget-empty", monkeypatch, {"projection": 1, "mapping": 1}, capacity=0
    )
    assert asyncio.run(ctl.execute_material(other, empty, api_key=KEY)) is None
    assert other.progress["phase"] == "BUDGET_SAVED" and not no_call.calls
