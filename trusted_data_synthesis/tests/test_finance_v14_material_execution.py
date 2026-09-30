"""V14 finite-scope CPU/temporary-wallet mocks only; no paid or live-wallet actions."""

import asyncio
import copy
import hashlib
import json
from types import SimpleNamespace

import httpx
import pytest
from test_finance_research_probe_provider import Client
from test_finance_unknown_abandonment import table
from test_finance_v10_budget import stopped_history, synthetic_parent  # noqa: F401
from test_finance_v12_budget_provider import clone, funded, registered  # noqa: F401
from test_finance_v13_material_execution import v13_seed  # noqa: F401
from test_finance_v13_material_protocol import bindings

from trusted_synthesis.finance_research import v13_budget as parent_budget
from trusted_synthesis.finance_research import v13_material_protocol as parent_protocol
from trusted_synthesis.finance_research import v14_budget as budget
from trusted_synthesis.finance_research import v14_material_controller as ctl
from trusted_synthesis.finance_research import v14_material_protocol as protocol
from trusted_synthesis.finance_research import v14_material_provider as provider
from trusted_synthesis.finance_research.contracts import (
    ProviderCallError,
    digest,
    invocation_identity,
)
from trusted_synthesis.finance_research.probe_budget import (
    BudgetUnavailable,
    DuplicateInvocation,
    _request_record_digest,
)
from trusted_synthesis.finance_research.providers import _json
from trusted_synthesis.finance_research.v13_material_registration import entry

PROTOCOL = "synthetic-v14-finite"
KEY = "CPU-only-not-real-secret"


def save(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(_json(value))
    return entry(path)


def call_args(ledger, eid, body):
    coords = invocation_identity(
        dict(run_id=ledger.run_id, episode_id=eid, attempt_index=1), turn_index=0
    )
    return dict(
        invocation_id=coords["invocation_id"],
        coordinates=coords,
        request=body,
        request_body=_json(body).encode(),
    )


@pytest.fixture(scope="module")
def residual_seed(tmp_path_factory, v13_seed):  # noqa: F811
    old_path, parent_plan, parent_requests, _ = v13_seed
    folder = tmp_path_factory.mktemp("synthetic-v14-residual")
    ledger = clone(old_path, folder / "wallet.sqlite")
    parent_budget.register_matrix(
        ledger,
        parent_plan,
        parent_budget.authorization_definition(parent_plan),
        backup_path=folder / "before-v13.sqlite",
    )
    lookup = {r["episode_id"]: r for r in parent_requests}
    old_jobs = [j for j in parent_plan["jobs"] if j["kind"] == "mapping"][:12]
    calls = []
    for job in old_jobs:
        body = (
            parent_protocol.request_body(lookup[job["episode_id"]])
            if job["episode_id"] in lookup
            else dict(
                model="deepseek-flash",
                max_tokens=job["max_output_tokens"],
                thinking={"type": "disabled"},
            )
        )
        call = call_args(ledger, job["episode_id"], body)
        ledger.reserve(**call)
        ledger.mark_dispatched(call["invocation_id"])
        calls.append((job, call))
    for _, call in calls:
        ledger.unknown(
            call["invocation_id"],
            reason=parent_budget.NETWORK_REASON,
            evidence=dict(
                exception_type="ReadError",
                service_response_received=False,
                budget_invocation_id=call["invocation_id"],
                budget_coordinates=call["coordinates"],
                request_sha256=digest(call["request"]),
            ),
        )
    parent_budget.acknowledge_connection_unknowns(
        ledger,
        protocol_id=parent_plan["protocol_identity"],
        expected_requests={c["invocation_id"]: digest(c["request"]) for _, c in calls},
    )
    network = [
        dict(
            task_id=j["task_id"],
            invocation_id=c["invocation_id"],
            original_ledger_record_sha256=_request_record_digest(
                ledger.request_record(c["invocation_id"])
            ),
        )
        for j, c in calls
    ]
    groups = parent_plan["fixed_task_slots"]
    common = [sid for slots in groups.values() for sid in slots]
    source = folder / "source-V13"
    seal = budget.bound(dict(schema="synthetic_complete_V13", expected_calls=1316))
    save(source / "completion_seal/record.json", seal)
    mp = pytest.MonkeyPatch()
    mp.setattr(budget, "SOURCE_SEAL_ID", seal["id"])
    parent_def = budget.bound(dict(candidate_slot_ids=common, fixed_task_slots=groups))
    parent_ref = save(source / "definition/record.json", parent_def)
    missing_tasks = [t for t, s in groups.items() if len(s) > 1][:64]
    review = budget.bound(
        dict(
            schema="v14_representation_review.v1",
            mapping_review_count=633,
            original_successes_preserved=325,
            original_success_partition_evidence_chi_unchanged=True,
            m=256,
            b=2,
            residual_projection_slot_ids=[common[0]],
            residual_mapping_task_ids=missing_tasks,
            network_unknown_task_ids=[r["task_id"] for r in network],
            network_unknown_sources=network,
        )
    )
    review_ref = save(folder / "representation_review/record.json", review)
    definition = budget.bound(
        dict(source_v13_definition=parent_ref, representation_review=review_ref)
    )
    definition_ref = save(folder / "definition/record.json", definition)
    views = parent_requests[1]["views"]
    requests = [
        protocol.prepare_projection(
            views[0], protocol_id=PROTOCOL, source_bindings=bindings([views[0]])
        ),
        protocol.prepare_mapping(views, protocol_id=PROTOCOL, source_bindings=bindings(views)),
    ]
    actual = {r["episode_id"]: r for r in requests}
    jobs = []
    for kind, ids in (("projection", [common[0]]), ("mapping", missing_tasks)):
        for identity in ids:
            task = (
                next(t for t, s in groups.items() if identity in s)
                if kind == "projection"
                else identity
            )
            slots = [identity] if kind == "projection" else groups[task]
            eid = budget.material_episode_id(PROTOCOL, kind, task, slots)
            body = (
                protocol.request_body(actual[eid])
                if eid in actual
                else dict(model="deepseek-flash", max_tokens=8192, thinking={"type": "disabled"})
            )
            reason = (
                "projection_completion"
                if kind == "projection"
                else "network_recovery_new_once"
                if task in review["network_unknown_task_ids"]
                else "mapping_completion"
            )
            jobs.append(
                dict(
                    kind=kind,
                    purpose=kind,
                    role=kind,
                    episode_id=eid,
                    slot_id=identity if kind == "projection" else None,
                    task_id=task,
                    slot_ids=slots,
                    authority_reason=reason,
                    max_output_tokens=body["max_tokens"],
                    request_sha256=digest(body),
                    request_body_sha256=hashlib.sha256(_json(body).encode()).hexdigest(),
                )
            )
    plan = budget.bound(
        dict(
            batch_id=budget.BATCH_ID,
            source_batch_id=budget.SOURCE_BATCH_ID,
            source_root=str(source),
            source_protocol_id=parent_plan["id"],
            source_review_seal_id=seal["id"],
            definition=definition_ref,
            representation_review=review_ref,
            model="deepseek-flash",
            protocol_identity=PROTOCOL,
            jobs=jobs,
            expected_requests=len(jobs),
            purpose_counts={"projection": 1, "mapping": 64},
            fixed_task_slots=groups,
            concurrency={"max": 16, "ramp": [{"settled_at_least": 0, "workers": 16}]},
        )
    )
    yield ledger.path, plan, requests, network
    mp.undo()


@pytest.fixture
def matrix(tmp_path, residual_seed):
    path, plan, requests, network = residual_seed
    ledger = clone(path, tmp_path / "wallet.sqlite")
    permit = budget.register_matrix(
        ledger,
        plan,
        budget.authorization_definition(plan),
        backup_path=tmp_path / "before-v14.sqlite",
    )
    return ledger, plan, requests, network, permit


def test_append_exact_residual_scope_caps_and_all_parent_holds_unchanged(matrix):
    ledger, plan, _, network, permit = matrix
    assert permit["job_count"] == 65 and permit["purpose_counts"] == {
        "projection": 1,
        "mapping": 64,
    }
    assert permit["parent_v13_permit_id"] and not permit["authorization"]["quotas_increased"]
    for name in ("requests", "counters", "v10_quotas"):
        assert table(ledger.path, name) == table(permit["backup"]["path"], name)
    for item in network:
        assert (
            _request_record_digest(ledger.request_record(item["invocation_id"]))
            == item["original_ledger_record_sha256"]
        )
    assert (
        budget.register_matrix(
            ledger,
            plan,
            budget.authorization_definition(plan),
            backup_path=permit["backup"]["path"],
        )
        == permit
    )
    assert ledger.snapshot()["effective_hard_cap_microcny"] == 2000000000


def test_residual_missing_job_or_wrong_network_authority_rejected_before_backup(
    tmp_path, residual_seed
):
    path, plan, _, _ = residual_seed
    ledger = clone(path, tmp_path / "wallet.sqlite")
    bad = copy.deepcopy(plan)
    job = next(j for j in bad["jobs"] if j["authority_reason"] == "network_recovery_new_once")
    job["authority_reason"] = "mapping_completion"
    bad = budget.bound({k: v for k, v in bad.items() if k != "id"})
    with pytest.raises(ValueError, match="recovery scope"):
        budget.register_matrix(
            ledger,
            bad,
            budget.authorization_definition(bad),
            backup_path=tmp_path / "absent.sqlite",
        )
    assert not (tmp_path / "absent.sqlite").exists()


def reply():
    from test_finance_v13_material_execution import response

    return response('{"invalid":true}')


def test_new_typed_request_settles_original_args_and_keeps_parent_network_unknown(matrix):
    ledger, _, requests, network, _ = matrix
    for request in requests:
        client = Client(reply())
        artifact = asyncio.run(
            provider.request_once(ledger=ledger, api_key=KEY, request=request, client=client)
        )
        row = ledger.request_record(artifact["budget_invocation_id"])
        record = provider.paid_record(request, artifact, row)
        assert (
            record["schema"] == "v14_paid_material_annotation.v1"
            and record["actual_model_call_receipt_verified"]
        )
        assert (
            not record["inspection"]["production_admitted"]
            and artifact["review_text"] == '{"invalid":true}'
        )
        assert provider.restore_settled(row, json.loads(_json(request))) == artifact
        with pytest.raises(DuplicateInvocation):
            asyncio.run(
                provider.request_once(ledger=ledger, api_key=KEY, request=request, client=client)
            )
        assert len(client.calls) == 1
    assert all(ledger.request_record(n["invocation_id"])["state"] == "UNKNOWN" for n in network)


def test_old_scope_and_attempt2_forbidden_and_reserved_continue_exact(matrix):
    ledger, _, requests, _, _ = matrix
    request = requests[0]
    body = protocol.request_body(request)
    old = call_args(ledger, "v13projection:" + "1" * 64, body)
    with pytest.raises(BudgetUnavailable):
        ledger.reserve(**old)
    call = call_args(ledger, request["episode_id"], body)
    ledger.reserve(**call)
    before = ledger.snapshot()["requests_reserved"]
    artifact = asyncio.run(
        provider.request_once(
            ledger=ledger,
            api_key=KEY,
            request=request,
            client=Client(reply()),
            resume_reserved=True,
        )
    )
    assert artifact["actual_model_calls"] == 1 and ledger.snapshot()["requests_reserved"] == before


def test_network_unknown_holds_permanent_no_automatic_resend(matrix):
    ledger, _, requests, _, _ = matrix
    request = requests[0]
    client = Client(failure=httpx.ReadError("synthetic only"))
    with pytest.raises(ProviderCallError):
        asyncio.run(
            provider.request_once(ledger=ledger, api_key=KEY, request=request, client=client)
        )
    iid = call_args(ledger, request["episode_id"], protocol.request_body(request))["invocation_id"]
    row = ledger.request_record(iid)
    before = ledger.snapshot()["held_microcny"]
    receipt = budget.acknowledge_connection_unknowns(
        ledger, protocol_id=PROTOCOL, expected_requests={iid: row["request_sha256"]}
    )
    assert (
        receipt["records"][0]["model_response"] is None
        and ledger.snapshot()["held_microcny"] == before
    )
    with pytest.raises(DuplicateInvocation):
        asyncio.run(
            provider.request_once(
                ledger=ledger, api_key=KEY, request=request, client=client, resume_reserved=True
            )
        )
    assert len(client.calls) == 1


def test_dynamic_residual_seal_requires_all_not_valid_subset(tmp_path):
    jobs = []
    terminals = {}
    for i, purpose in enumerate(("projection", "mapping")):
        eid = "v14" + purpose + ":" + digest(i)
        job = dict(
            episode_id=eid,
            role=purpose,
            kind=purpose,
            purpose=purpose,
            task_id="task",
            slot_id="slot" if i == 0 else None,
            slot_ids=["slot"] if i == 0 else ["slot", "other"],
            request_id="request" + str(i),
            request={},
            authority_reason="test",
        )
        jobs.append(job)
    ctx = SimpleNamespace(
        output=tmp_path,
        jobs=jobs,
        plan=dict(
            id="CPU-plan",
            protocol_identity=PROTOCOL,
            source_review_seal_id="source",
            expected_requests=2,
            purpose_counts={"projection": 1, "mapping": 1},
            representation_review={},
        ),
    )
    for job in jobs:
        record = ctl.bound(
            dict(
                schema="v14_paid_material_annotation.v1",
                actual_model_call_receipt_verified=True,
                inspection={
                    "usable": False,
                    "mapping_status": "unknown",
                    "mapping_admitted": False,
                },
            )
        )
        directory = ctl.job_directory(tmp_path, job)
        ctl.persist(directory / "record", record)
        terminals[job["episode_id"]] = ctl._terminal(ctx, job, record, "paid_model_return")
    with pytest.raises(ValueError, match="partial"):
        ctl.freeze_completion_seal(ctx, {jobs[0]["episode_id"]: terminals[jobs[0]["episode_id"]]})
    seal = ctl.freeze_completion_seal(ctx, terminals)
    assert (
        seal["expected_calls"] == 2
        and seal["actual_returns"] == 2
        and not seal["production_admitted"]
    )
    assert seal["projection_usable_calls"] == seal["mapping_complete_calls"] == 0
