"""Three-call CPU-only wallet/HTTP controls with preserved real SQLite accounting."""

import asyncio
import copy
import hashlib
import json

import pytest
from test_finance_research_probe_provider import Client
from test_finance_unknown_abandonment import table
from test_finance_v10_budget import stopped_history, synthetic_parent  # noqa: F401
from test_finance_v12_budget_provider import clone, funded, registered  # noqa: F401
from test_finance_v13_material_execution import response, v13_seed  # noqa: F401
from test_finance_v13_material_protocol import bindings, rebound
from test_finance_v14_material_execution import residual_seed, save  # noqa: F401
from test_finance_v15_mapping_execution import mapping_seed  # noqa: F401
from test_finance_v16_adjudication import revised_views
from test_finance_v16_execution import six_seed  # noqa: F401

from trusted_synthesis.finance_research import v15_mapping_protocol as old_protocol
from trusted_synthesis.finance_research import v16_adjudication_protocol as parent_protocol
from trusted_synthesis.finance_research import v16_budget as parent_budget
from trusted_synthesis.finance_research import v16_controller as core
from trusted_synthesis.finance_research import v16_registration as parent_registration
from trusted_synthesis.finance_research import v17_adjudication_protocol as protocol
from trusted_synthesis.finance_research import v17_budget as budget
from trusted_synthesis.finance_research import v17_controller as ctl
from trusted_synthesis.finance_research import v17_provider as provider
from trusted_synthesis.finance_research import v17_registration as registration
from trusted_synthesis.finance_research.contracts import (
    ProviderCallError,
    digest,
    invocation_identity,
)
from trusted_synthesis.finance_research.probe_budget import BudgetUnavailable, DuplicateInvocation
from trusted_synthesis.finance_research.providers import _json

KEY = "CPU-only-not-an-actual-key-v17"


@pytest.fixture(scope="module")
def three_seed(tmp_path_factory, six_seed):  # noqa: F811
    path, parent_plan, _, parent_boundary = six_seed
    folder = tmp_path_factory.mktemp("v17-wallet-seed")
    ledger = clone(path, folder / "wallet.sqlite")
    with pytest.MonkeyPatch.context() as mp:
        mp.setattr(parent_registration, "original_authorities", lambda _: parent_boundary)
        parent_budget.register_matrix(
            ledger,
            parent_plan,
            parent_budget.authorization_definition(parent_plan),
            backup_path=folder / "before-v16.sqlite",
        )
    groups = copy.deepcopy(parent_plan["fixed_task_slots"])
    fixed = parent_plan["fixed_unresolved_task_ids"][:3]
    # The old CPU fixture has only 4-member groups. This explicitly synthetic
    # extra roster row creates the required 4/5/4 shape in this temporary wallet.
    # It is NOT a production-source claim or a change to any real experiment.
    extra = "v10gen:" + digest("CPU-explicit-v17-extra-fifth-package")
    groups[fixed[1]].append(extra)
    with ledger._transaction() as db:
        db.execute(
            "INSERT INTO v10_episode_roster VALUES (?,?,?,?,?)",
            (extra, "generation", fixed[1], extra, None),
        )
    assert [len(groups[t]) for t in fixed] == [4, 5, 4]
    parent_ref = save(folder / "predecessor/registration/record.json", parent_plan)
    template = revised_views()[0]
    latest, failed = {}, {}
    for task in fixed:
        views = []
        for slot in groups[task]:
            view = json.loads(json.dumps(template).replace(template["slot_id"], slot))
            view["task_id"] = task
            views.append(rebound(view))
        old_req = old_protocol.prepare_mapping(
            views, protocol_id="CPU-v17-synthetic-v15-parent", source_bindings=bindings(views)
        )
        old = budget.bound(
            dict(
                schema="v15_paid_material_annotation.v1",
                actual_model_call_receipt_verified=True,
                purpose="mapping",
                task_id=task,
                slot_ids=groups[task],
                request=old_req,
                artifact=dict(review_text="{}"),
                inspection=dict(mapping_admitted=False, errors=["CPU-only original failure"]),
                synthetic_test_source_only=True,
            )
        )
        parent_req = parent_protocol.prepare_mapping(
            views,
            latest_record=old,
            protocol_id="CPU-v17-synthetic-v16-parent",
            source_bindings=bindings(views),
        )
        art = dict(review_text="{}", finish_reason="tool_calls", review_format_error=None)
        latest[task] = budget.bound(
            dict(
                schema="v16_paid_material_annotation.v1",
                actual_model_call_receipt_verified=True,
                purpose="mapping",
                task_id=task,
                slot_ids=groups[task],
                request=parent_req,
                artifact=art,
                inspection=parent_protocol.inspect_reply(parent_req, art),
                synthetic_test_source_only=True,
            )
        )
        failed[task] = save(
            folder / "predecessor/failures" / digest(task) / "record.json", latest[task]
        )
    inherited = {t: {"synthetic_preserved_authority": t} for t in groups if t not in fixed}
    assert len(inherited) == 741
    definition = budget.bound(
        dict(
            schema="CPU-synthetic-three-source-boundary",
            predecessor_registration=parent_ref,
            inherited_mapping_authorities=inherited,
            previous_failed_authorities=failed,
        )
    )
    definition_ref = save(folder / "definition/record.json", definition)
    requests, jobs = [], []
    for task in fixed:
        req = protocol.prepare_mapping(
            latest[task]["request"]["views"],
            latest_record=latest[task],
            protocol_id=definition["id"],
            source_bindings=dict(task_slot_ids=groups[task], synthetic_test_source=True),
        )
        body = protocol.request_body(req)
        req_ref = save(folder / "requests" / digest(task) / "record.json", req)
        jobs.append(
            dict(
                kind="mapping",
                purpose="mapping",
                role="mapping",
                task_id=task,
                slot_id=None,
                slot_ids=req["slot_ids"],
                episode_id=req["episode_id"],
                request_id=req["id"],
                request=req_ref,
                max_output_tokens=req["max_output_tokens"],
                request_sha256=digest(body),
                request_body_sha256=hashlib.sha256(_json(body).encode()).hexdigest(),
            )
        )
        requests.append(req)
    plan = budget.bound(
        dict(
            schema="v17_three_task_adjudication_plan.v1",
            batch_id=budget.BATCH_ID,
            predecessor_root=str(folder / "predecessor"),
            predecessor_registration=parent_ref,
            source_protocol_id=parent_plan["id"],
            definition=definition_ref,
            fixed_unresolved_task_ids=fixed,
            fixed_task_slots=groups,
            protocol_identity=definition["id"],
            jobs=jobs,
            model="deepseek-flash",
            expected_requests=3,
            purpose_counts={"mapping": 3},
            concurrency={"max": 3},
        )
    )
    # Only financial/semantic source closure is mocked. The permit chain, all
    # original UNKNOWN holds, quota counters, raw bytes and settlements are SQLite.
    boundary = parent_plan, dict(fixed_task_slots=groups), inherited, failed
    return ledger.path, plan, requests, boundary


@pytest.fixture
def matrix(tmp_path, three_seed, monkeypatch):
    path, plan, requests, boundary = three_seed
    ledger = clone(path, tmp_path / "wallet.sqlite")
    monkeypatch.setattr(registration, "original_authorities", lambda _: boundary)
    before = ledger.snapshot()
    permit = budget.register_matrix(
        ledger,
        plan,
        budget.authorization_definition(plan),
        backup_path=tmp_path / "before-v17.sqlite",
    )
    return ledger, plan, requests, permit, before


def call_args(ledger, req, *, episode=None, attempt=1, turn=0, body=None):
    body = protocol.request_body(req) if body is None else body
    coordinates = invocation_identity(
        dict(run_id=ledger.run_id, episode_id=episode or req["episode_id"], attempt_index=attempt),
        turn_index=turn,
    )
    return dict(
        invocation_id=coordinates["invocation_id"],
        coordinates=coordinates,
        request=body,
        request_body=_json(body).encode(),
    )


def valid_response(req):
    state = dict(
        members=list(req["aliases"]["packages"]),
        basis="CPU-only explicit judgment.",
        chi=0,
        evidence=[
            next(k for k in req["mapping_domains"]["evidence_ids"] if k.startswith(p + ":u"))
            for p in req["aliases"]["packages"]
        ],
        changes=[],
    )
    return response(
        _json(dict(states=[state], resolution="CPU-only new explicit judgment.", unresolved=""))
    )


class TaskClient(Client):
    def __init__(self, requests):
        super().__init__()
        self.by_task = {r["task_id"]: valid_response(r) for r in requests}

    async def post(self, url, **kwargs):
        body = json.loads(kwargs["content"])
        task = json.loads(body["messages"][1]["content"])["task_id"]
        self.response = self.by_task[task]
        return await super().post(url, **kwargs)


def test_append_three_inherits_exact_v16_permit_and_preserves_wallet_rows(matrix):
    ledger, plan, _, permit, before = matrix
    with ledger._transaction() as db:
        parent = parent_budget.read_matrix_permit(db, ledger.config)
        assert budget.read_matrix_permit(db, ledger.config) == permit
    assert permit["job_count"] == 3
    assert permit["parent_v16_permit_id"] == parent["id"]
    assert permit["source_plan_id"] == parent["plan_id"] == plan["source_protocol_id"]
    assert permit["predecessor_registration"] == plan["predecessor_registration"]
    assert permit["authorization"]["exact_new_call_count"] == 3
    assert permit["authorization"]["original_packages"] == 13
    assert not permit["authorization"]["quotas_increased"]
    assert (
        ledger.snapshot() == before
        and before["unknown_requests"] > 0
        and before["held_microcny"] > 0
    )
    for name in ("requests", "counters", "v10_quotas"):
        assert table(ledger.path, name) == table(permit["backup"]["path"], name)
    assert (
        budget.register_matrix(
            ledger,
            plan,
            budget.authorization_definition(plan),
            backup_path=permit["backup"]["path"],
        )
        == permit
    )


def test_exact_three_attempt1_turn0_bytes_model_cap_and_namespace_only(matrix):
    ledger, plan, requests, _, before = matrix
    req = requests[0]
    outside = next(
        t for t in plan["fixed_task_slots"] if t not in plan["fixed_unresolved_task_ids"]
    )
    for change in (
        dict(episode=budget.mapping_episode_id(plan["protocol_identity"], outside)),
        dict(episode="v16mapping:" + "0" * 64),
        dict(attempt=2),
        dict(turn=1),
        dict(body=protocol.request_body(req) | {"temperature": 0.5}),
        dict(body=protocol.request_body(req) | {"model": "deepseek-v4-pro"}),
        dict(body=protocol.request_body(req) | {"max_tokens": 16384}),
    ):
        with pytest.raises((BudgetUnavailable, ValueError)):
            ledger.reserve(**call_args(ledger, req, **change))
    assert ledger.snapshot() == before
    for item in requests:
        ledger.reserve(**call_args(ledger, item))
    assert ledger.snapshot()["requests_reserved"] == before["requests_reserved"] + 3
    with pytest.raises(DuplicateInvocation):
        ledger.reserve(**call_args(ledger, req))


def test_changed_inherited_authority_cannot_register_even_when_job_count_is_three(
    tmp_path, three_seed, monkeypatch
):
    path, plan, _, boundary = three_seed
    ledger = clone(path, tmp_path / "wallet.sqlite")
    altered = copy.deepcopy(boundary[2])
    altered[next(iter(altered))] = {"not_the_preserved_authority": True}
    monkeypatch.setattr(
        registration,
        "original_authorities",
        lambda _: (boundary[0], boundary[1], altered, boundary[3]),
    )
    before = ledger.snapshot()
    with pytest.raises(ValueError, match="741"):
        budget.register_matrix(
            ledger,
            plan,
            budget.authorization_definition(plan),
            backup_path=tmp_path / "absent.sqlite",
        )
    assert ledger.snapshot() == before and not (tmp_path / "absent.sqlite").exists()


def test_v17_provider_exact_raw_response_and_settled_replay_do_not_use_v16_schema(matrix):
    ledger, _, requests, _, _ = matrix
    req, client = requests[0], Client(valid_response(requests[0]))
    art = asyncio.run(provider.request_once(ledger=ledger, api_key=KEY, request=req, client=client))
    row = ledger.request_record(art["budget_invocation_id"])
    record = provider.paid_record(req, art, row)
    assert art["schema"] == "v17_settled_material_artifact.v1"
    assert record["schema"] == "v17_paid_material_annotation.v1"
    assert record["inspection"]["schema"] == "v17_adjudication_inspection.v1"
    assert record["inspection"]["mapping_admitted"] and record["actual_model_call_receipt_verified"]
    assert provider.restore_settled(row, copy.deepcopy(req)) == art
    assert (
        row["request_body"]
        == client.calls[0][1]["content"]
        == _json(protocol.request_body(req)).encode()
    )
    assert row["response_body"] == json.dumps(client.response).encode()
    assert KEY.encode() not in row["request_body"] + row["response_body"]
    with pytest.raises(DuplicateInvocation):
        asyncio.run(provider.request_once(ledger=ledger, api_key=KEY, request=req, client=client))
    assert len(client.calls) == 1


def test_confirmed_unsent_v17_reservation_dispatches_once_without_second_hold(matrix):
    ledger, _, requests, _, before = matrix
    req = requests[0]
    args = call_args(ledger, req)
    ledger.reserve(**args)
    client = Client(valid_response(req))
    art = asyncio.run(
        provider.request_once(
            ledger=ledger, api_key=KEY, request=req, client=client, resume_reserved=True
        )
    )
    assert art["budget_invocation_id"] == args["invocation_id"]
    assert ledger.snapshot()["requests_reserved"] == before["requests_reserved"] + 1
    assert len(client.calls) == 1


@pytest.mark.parametrize("failure", ["timeout", "wrong_model", "missing_usage"])
def test_unknown_retains_old_and_new_holds_stops_and_does_not_retry(matrix, failure):
    ledger, _, requests, _, before = matrix
    response_body = valid_response(requests[0])
    if failure == "wrong_model":
        response_body["model"] = "deepseek-v4-pro"
    elif failure == "missing_usage":
        response_body.pop("usage")
    client = Client(
        response_body, failure=TimeoutError("CPU-only timeout") if failure == "timeout" else None
    )
    with pytest.raises(ProviderCallError):
        asyncio.run(
            provider.request_once(ledger=ledger, api_key=KEY, request=requests[0], client=client)
        )
    after = ledger.snapshot()
    assert after["unknown_requests"] == before["unknown_requests"] + 1
    assert after["held_microcny"] > before["held_microcny"] and after["halt"]
    with pytest.raises(BudgetUnavailable):
        asyncio.run(
            provider.request_once(ledger=ledger, api_key=KEY, request=requests[1], client=client)
        )
    assert len(client.calls) == 1


def test_changed_request_model_is_rejected_before_reserve_or_http(matrix):
    ledger, _, requests, _, before = matrix
    req = copy.deepcopy(requests[0])
    req["model"] = "deepseek-v4-pro"
    req = protocol.bound({k: v for k, v in req.items() if k != "id"})
    client = Client()
    with pytest.raises(ValueError, match="flash"):
        asyncio.run(provider.request_once(ledger=ledger, api_key=KEY, request=req, client=client))
    assert not client.calls and ledger.snapshot() == before


def test_controller_exact_three_terminals_then_cold_replay_without_resampling(
    tmp_path, matrix, monkeypatch
):
    ledger, plan, requests, _, before = matrix
    output, client = tmp_path / "wave", TaskClient(requests)
    result = asyncio.run(ctl.execute(output, plan, ledger, api_key=KEY, client=client))
    assert (
        result["phase"] == "COMPLETE" and result["actual_returns"] == result["usable_returns"] == 3
    )
    assert result["schema"] == "v17_three_adjudication_controller_result.v1"
    seal = registration.read_ref(result["completion_seal"])
    assert (
        seal["schema"] == "v17_three_adjudication_completion_seal.v1"
        and len(seal["terminals"]) == 3
    )
    assert (
        len(client.calls) == 3
        and ledger.snapshot()["requests_reserved"] == before["requests_reserved"] + 3
    )
    monkeypatch.setattr(registration, "checked_plan", lambda _: plan)
    monkeypatch.setattr(
        registration, "ledger_for", lambda _: pytest.fail("closed wave must not reopen wallet")
    )
    assert ctl.run(output) == result
    forbidden = Client(failure=AssertionError("no second paid sample"))
    recovered = asyncio.run(
        ctl.execute(tmp_path / "recovered", plan, ledger, api_key=KEY, client=forbidden)
    )
    assert recovered["actual_returns"] == recovered["usable_returns"] == 3 and not forbidden.calls


def test_controller_transport_failure_stops_remaining_and_saved_failure_never_retries(
    tmp_path, matrix, monkeypatch
):
    ledger, plan, _, _, before = matrix
    output, client = tmp_path / "failed-wave", Client(failure=TimeoutError("CPU timeout"))
    result = asyncio.run(ctl.execute(output, plan, ledger, api_key=KEY, client=client))
    assert result["phase"] == "SAVED_FAILURE_NO_RETRY" and result["actual_returns"] == 0
    assert result["completion_seal"] is None and len(result["errors"]) == 3
    assert (
        len(client.calls) == 1
        and ledger.snapshot()["unknown_requests"] == before["unknown_requests"] + 1
    )
    monkeypatch.setattr(registration, "checked_plan", lambda _: plan)
    monkeypatch.setattr(
        registration, "ledger_for", lambda _: pytest.fail("failure cannot redispatch")
    )
    assert ctl.run(output) == result and len(client.calls) == 1


def test_paid_missing_chi_remains_settled_failed_and_retains_original_raw(matrix):
    ledger, _, requests, _, _ = matrix
    req = requests[0]
    value = valid_response(req)
    function = value["choices"][0]["message"]["tool_calls"][0]["function"]
    body = json.loads(function["arguments"])
    del body["states"][0]["chi"]
    body["states"][0]["basis"] = "chi=1 in prose is not the mandatory chi field."
    function["arguments"] = _json(body)
    client = Client(value)
    art = asyncio.run(provider.request_once(ledger=ledger, api_key=KEY, request=req, client=client))
    row = ledger.request_record(art["budget_invocation_id"])
    record = provider.paid_record(req, art, row)
    assert row["state"] == "SETTLED" and art["actual_model_calls"] == 1
    assert not record["inspection"]["mapping_admitted"]
    assert record["inspection"]["chi_by_state"] == {} and record["inspection"]["errors"]
    assert art["review_text"] == function["arguments"] and len(client.calls) == 1


def test_controller_requires_three_jobs_before_wallet_or_network(tmp_path, matrix):
    ledger, plan, _, _, before = matrix
    altered = dict(plan, expected_requests=6)
    client = Client()
    with pytest.raises(ValueError, match="exact wave"):
        asyncio.run(
            ctl.execute(tmp_path / "wrong-count", altered, ledger, api_key=KEY, client=client)
        )
    assert ledger.snapshot() == before and not client.calls


def test_deployment_reentry_retains_original_permit_timestamp_and_budget(
    tmp_path, three_seed, monkeypatch
):
    path, plan, _, boundary = three_seed
    output = tmp_path / "deploy"
    output.mkdir()
    ledger = clone(path, tmp_path / "wallet.sqlite")
    monkeypatch.setattr(registration, "original_authorities", lambda _: boundary)
    monkeypatch.setattr(registration, "checked_plan", lambda _: plan)
    monkeypatch.setattr(registration, "ledger_for", lambda _: ledger)
    first = ctl.deploy(output)
    raw, before = (output / "deployment/record.json").read_bytes(), ledger.snapshot()
    monkeypatch.setattr(core, "now", lambda: "2099-01-01T00:00:00+00:00")
    assert ctl.deploy(output) == first and (output / "deployment/record.json").read_bytes() == raw
    assert first["schema"] == "v17_three_deployment.v1" and ledger.snapshot() == before
