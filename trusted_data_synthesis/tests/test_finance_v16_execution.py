"""Six-task temporary-wallet/mock HTTP checks, never real API/Student evidence."""

import asyncio
import copy
import hashlib

import pytest
from test_finance_research_probe_provider import Client
from test_finance_unknown_abandonment import table
from test_finance_v10_budget import stopped_history, synthetic_parent  # noqa: F401
from test_finance_v10_process_review import fixture as original_fixture
from test_finance_v12_budget_provider import clone, funded, registered  # noqa: F401
from test_finance_v13_material_execution import response, v13_seed  # noqa: F401
from test_finance_v13_material_protocol import bindings
from test_finance_v14_material_execution import residual_seed, save  # noqa: F401
from test_finance_v15_mapping_execution import mapping_seed  # noqa: F401

from trusted_synthesis.finance_research import v11_process_review as original
from trusted_synthesis.finance_research import v15_budget as parent_budget
from trusted_synthesis.finance_research import v15_mapping_protocol as previous
from trusted_synthesis.finance_research import v16_adjudication_protocol as protocol
from trusted_synthesis.finance_research import v16_budget as budget
from trusted_synthesis.finance_research import v16_controller as ctl
from trusted_synthesis.finance_research import v16_provider as provider
from trusted_synthesis.finance_research import v16_registration as registration
from trusted_synthesis.finance_research.contracts import (
    ProviderCallError,
    digest,
    invocation_identity,
)
from trusted_synthesis.finance_research.probe_budget import BudgetUnavailable, DuplicateInvocation
from trusted_synthesis.finance_research.providers import _json

KEY = "CPU-only-not-an-actual-key-v16"


@pytest.fixture(scope="module")
def six_seed(tmp_path_factory, mapping_seed):  # noqa: F811
    path, parent_plan, _, _, _ = mapping_seed
    folder = tmp_path_factory.mktemp("v16-wallet-seed")
    ledger = clone(path, folder / "wallet.sqlite")
    parent_budget.register_matrix(
        ledger,
        parent_plan,
        parent_budget.authorization_definition(parent_plan),
        backup_path=folder / "before-v15.sqlite",
    )
    groups = parent_plan["fixed_task_slots"]
    fixed = list(groups)[:6]
    assert sum(len(groups[t]) for t in fixed) == 24
    parent_ref = save(folder / "source/registration/record.json", parent_plan)
    failed, latest = {}, {}
    for task in fixed:
        episode, old, _ = original_fixture()
        episode = episode.model_copy(update={"task_id": task})
        views = [
            original.prepare_review_request(
                episode,
                slot_id=sid,
                role="A",
                native_result=old["native_result"],
                integrity=old["integrity"],
            )["trajectory"]
            for sid in groups[task]
        ]
        req = previous.prepare_mapping(
            views, protocol_id="synthetic-prior-v15-judgment", source_bindings=bindings(views)
        )
        latest[task] = budget.bound(
            dict(
                schema="v15_paid_material_annotation.v1",
                actual_model_call_receipt_verified=True,
                purpose="mapping",
                task_id=task,
                slot_ids=groups[task],
                request=req,
                artifact=dict(review_text="{}"),
                inspection=dict(mapping_admitted=False, errors=["CPU synthetic missing members"]),
                synthetic_test_source_only=True,
            )
        )
        failed[task] = save(folder / "source/failures" / digest(task) / "record.json", latest[task])
    inherited = {t: {"synthetic_preserved_authority": t} for t in groups if t not in fixed}
    definition = budget.bound(
        dict(
            schema="CPU-synthetic-six-source-boundary",
            source_registration=parent_ref,
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
            schema="v16_six_task_adjudication_plan.v1",
            batch_id=budget.BATCH_ID,
            source_root=str(folder / "source"),
            source_registration=parent_ref,
            source_protocol_id=parent_plan["id"],
            definition=definition_ref,
            fixed_unresolved_task_ids=fixed,
            fixed_task_slots=groups,
            protocol_identity=definition["id"],
            jobs=jobs,
            model="deepseek-flash",
            expected_requests=6,
            purpose_counts={"mapping": 6},
            concurrency={"max": 6},
        )
    )
    # Only the semantic/source boundary is synthetic; all permit chains,
    # reservations, original UNKNOWN rows, counters and settlements are real SQLite.
    boundary = parent_plan, dict(fixed_task_slots=groups), inherited, failed
    return ledger.path, plan, requests, boundary


@pytest.fixture
def matrix(tmp_path, six_seed, monkeypatch):
    path, plan, requests, boundary = six_seed
    ledger = clone(path, tmp_path / "wallet.sqlite")
    monkeypatch.setattr(registration, "original_authorities", lambda source: boundary)
    before = ledger.snapshot()
    permit = budget.register_matrix(
        ledger,
        plan,
        budget.authorization_definition(plan),
        backup_path=tmp_path / "before-v16.sqlite",
    )
    return ledger, plan, requests, permit, before


def call_args(ledger, request, *, episode=None, attempt=1, turn=0, body=None):
    body = protocol.request_body(request) if body is None else body
    coords = invocation_identity(
        dict(
            run_id=ledger.run_id, episode_id=episode or request["episode_id"], attempt_index=attempt
        ),
        turn_index=turn,
    )
    return dict(
        invocation_id=coords["invocation_id"],
        coordinates=coords,
        request=body,
        request_body=_json(body).encode(),
    )


def valid_response(request):
    evidence = []
    for package in request["aliases"]["packages"]:
        evidence.append(
            next(
                key
                for key in request["mapping_domains"]["evidence_ids"]
                if key.startswith(package + ":u")
            )
        )
    return response(
        _json(
            dict(
                states=[
                    dict(
                        members=list(request["aliases"]["packages"]),
                        basis="CPU common derivation.",
                        chi=0,
                        evidence=evidence,
                        changes=[],
                    )
                ],
                resolution=(
                    "CPU source supplies the exact members omitted by the prior synthetic return."
                ),
                unresolved="",
            )
        )
    )


def test_append_six_preserves_all_unknown_holds_limits_and_existing_rows(matrix):
    ledger, plan, _, permit, before = matrix
    assert permit["job_count"] == 6 and permit["parent_v15_permit_id"]
    assert permit["authorization"]["exact_new_call_count"] == 6
    assert not permit["authorization"]["quotas_increased"]
    assert not permit["authorization"]["training_authorized_by_this_permit"]
    assert ledger.snapshot() == before
    assert before["unknown_requests"] > 0 and before["held_microcny"] > 0
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


def test_only_exact_six_bytes_attempt1_turn0_no_old_or_other_task(matrix):
    ledger, plan, requests, _, before = matrix
    request = requests[0]
    outside = next(
        t for t in plan["fixed_task_slots"] if t not in plan["fixed_unresolved_task_ids"]
    )
    for opts in (
        dict(episode=budget.mapping_episode_id(plan["protocol_identity"], outside)),
        dict(episode="v15mapping:" + "0" * 64),
        dict(attempt=2),
        dict(turn=1),
        dict(body=protocol.request_body(request) | {"temperature": 0.5}),
        dict(body=protocol.request_body(request) | {"model": "deepseek-v4-pro"}),
        dict(body=protocol.request_body(request) | {"max_tokens": 16384}),
    ):
        with pytest.raises((BudgetUnavailable, ValueError)):
            ledger.reserve(**call_args(ledger, request, **opts))
    assert ledger.snapshot() == before
    for req in requests:
        ledger.reserve(**call_args(ledger, req))
    assert ledger.snapshot()["requests_reserved"] - before["requests_reserved"] == 6
    with pytest.raises(DuplicateInvocation):
        ledger.reserve(**call_args(ledger, request))


def test_provider_exact_payload_settlement_and_cold_replay_no_second_call(matrix):
    ledger, _, requests, _, _ = matrix
    request = requests[0]
    client = Client(valid_response(request))
    artifact = asyncio.run(
        provider.request_once(
            ledger=ledger,
            api_key=KEY,
            request=request,
            client=client,
        )
    )
    row = ledger.request_record(artifact["budget_invocation_id"])
    paid = provider.paid_record(request, artifact, row)
    assert paid["inspection"]["mapping_admitted"]
    assert paid["actual_model_call_receipt_verified"] and not artifact["content_repair_performed"]
    assert (
        artifact["review_text"]
        == client.response["choices"][0]["message"]["tool_calls"][0]["function"]["arguments"]
    )
    assert provider.restore_settled(row, copy.deepcopy(request)) == artifact
    assert (
        row["request_body"]
        == client.calls[0][1]["content"]
        == _json(protocol.request_body(request)).encode()
    )
    assert KEY.encode() not in row["request_body"] + row["response_body"]
    with pytest.raises(DuplicateInvocation):
        asyncio.run(
            provider.request_once(ledger=ledger, api_key=KEY, request=request, client=client)
        )
    assert len(client.calls) == 1


def test_reserved_unsent_continues_once_without_second_reservation(matrix):
    ledger, _, requests, _, before = matrix
    request = requests[0]
    args = call_args(ledger, request)
    ledger.reserve(**args)
    client = Client(valid_response(request))
    artifact = asyncio.run(
        provider.request_once(
            ledger=ledger,
            api_key=KEY,
            request=request,
            client=client,
            resume_reserved=True,
        )
    )
    assert artifact["budget_invocation_id"] == args["invocation_id"]
    assert ledger.snapshot()["requests_reserved"] == before["requests_reserved"] + 1
    assert len(client.calls) == 1


@pytest.mark.parametrize("failure", ["timeout", "wrong_model", "missing_usage"])
def test_unknown_retains_new_and_old_holds_stops_no_retry(matrix, failure):
    ledger, _, requests, _, before = matrix
    value = valid_response(requests[0])
    if failure == "wrong_model":
        value["model"] = "deepseek-v4-pro"
    if failure == "missing_usage":
        value.pop("usage")
    client = Client(value, failure=TimeoutError("CPU timeout") if failure == "timeout" else None)
    with pytest.raises(ProviderCallError):
        asyncio.run(
            provider.request_once(ledger=ledger, api_key=KEY, request=requests[0], client=client)
        )
    after = ledger.snapshot()
    assert after["unknown_requests"] == before["unknown_requests"] + 1
    assert after["held_microcny"] > before["held_microcny"] and after["halt"]
    assert len(client.calls) == 1
    with pytest.raises(BudgetUnavailable):
        asyncio.run(
            provider.request_once(ledger=ledger, api_key=KEY, request=requests[1], client=client)
        )
    assert len(client.calls) == 1


def test_changed_request_model_rejected_before_reserve_or_network(matrix):
    ledger, _, requests, _, before = matrix
    request = copy.deepcopy(requests[0])
    request["model"] = "deepseek-v4-pro"
    request = protocol.bound({k: v for k, v in request.items() if k != "id"})
    client = Client()
    with pytest.raises(ValueError, match="deepseek-flash"):
        asyncio.run(
            provider.request_once(ledger=ledger, api_key=KEY, request=request, client=client)
        )
    assert not client.calls and ledger.snapshot() == before


def test_controller_six_once_and_settled_cold_replay_without_network(tmp_path, matrix, monkeypatch):
    ledger, plan, requests, _, before = matrix
    # Every task has the same synthetic four-package public layout.
    client = Client(valid_response(requests[0]))
    output = tmp_path / "wave"
    result = asyncio.run(ctl.execute(output, plan, ledger, api_key=KEY, client=client))
    assert (
        result["phase"] == "COMPLETE" and result["actual_returns"] == result["usable_returns"] == 6
    )
    assert len(client.calls) == 6 and result["completion_seal"]
    assert ledger.snapshot()["requests_reserved"] == before["requests_reserved"] + 6
    monkeypatch.setattr(ctl, "checked_plan", lambda _: plan)
    monkeypatch.setattr(
        ctl, "ledger_for", lambda _: pytest.fail("closed wave must not reopen wallet")
    )
    assert ctl.run(output) == result
    # Simulate a separate recovered artifact directory using the same settled
    # requests: exact settled replay produces all six records without resampling.
    forbidden = Client(failure=AssertionError("settled records must never be sent again"))
    recovered = asyncio.run(
        ctl.execute(tmp_path / "recovered", plan, ledger, api_key=KEY, client=forbidden)
    )
    assert recovered["actual_returns"] == recovered["usable_returns"] == 6
    assert not forbidden.calls


def test_controller_transport_failure_stops_unsent_and_cold_run_never_retries(
    tmp_path, matrix, monkeypatch
):
    ledger, plan, _, _, before = matrix
    client = Client(failure=TimeoutError("CPU first-call failure"))
    output = tmp_path / "failed-wave"
    result = asyncio.run(ctl.execute(output, plan, ledger, api_key=KEY, client=client))
    assert result["phase"] == "SAVED_FAILURE_NO_RETRY"
    assert result["actual_returns"] == 0 and len(result["errors"]) == 6
    assert len(client.calls) == 1 and result["completion_seal"] is None
    assert ledger.snapshot()["unknown_requests"] == before["unknown_requests"] + 1
    assert ledger.snapshot()["requests_reserved"] == before["requests_reserved"] + 1
    monkeypatch.setattr(ctl, "checked_plan", lambda _: plan)
    monkeypatch.setattr(
        ctl, "ledger_for", lambda _: pytest.fail("saved failure forbids new dispatch")
    )
    assert ctl.run(output) == result and len(client.calls) == 1


def test_controller_recovers_after_seal_before_result_without_rewriting_or_resending(
    tmp_path, matrix, monkeypatch
):
    ledger, plan, requests, _, _ = matrix
    output = tmp_path / "interrupted-closeout"
    client = Client(valid_response(requests[0]))
    original_persist = ctl.persist

    def interrupt_result(directory, *args, **kwargs):
        if directory.name == "controller_result":
            raise OSError("CPU simulated crash after durable completion seal")
        return original_persist(directory, *args, **kwargs)

    monkeypatch.setattr(ctl, "persist", interrupt_result)
    with pytest.raises(OSError, match="durable completion seal"):
        asyncio.run(ctl.execute(output, plan, ledger, api_key=KEY, client=client))
    seal_path = output / "completion_seal/record.json"
    sealed_bytes = seal_path.read_bytes()
    assert len(client.calls) == 6 and not (output / "controller_result/record.json").exists()
    before = ledger.snapshot()
    monkeypatch.setattr(ctl, "persist", original_persist)
    monkeypatch.setattr(ctl, "now", lambda: "2099-01-01T00:00:00+00:00")
    forbidden = Client(failure=AssertionError("settled calls cannot be repeated"))
    result = asyncio.run(ctl.execute(output, plan, ledger, api_key=KEY, client=forbidden))
    assert result["existing_completion_seal_reused"]
    assert result["actual_returns"] == result["usable_returns"] == 6
    assert seal_path.read_bytes() == sealed_bytes
    assert ledger.snapshot() == before and not forbidden.calls


def test_deployment_reentry_keeps_original_timestamp_permit_and_budget(
    tmp_path, six_seed, monkeypatch
):
    path, plan, _, boundary = six_seed
    output = tmp_path / "deployment"
    output.mkdir()
    ledger = clone(path, tmp_path / "deployment-wallet.sqlite")
    monkeypatch.setattr(registration, "original_authorities", lambda source: boundary)
    monkeypatch.setattr(ctl, "checked_plan", lambda _: plan)
    monkeypatch.setattr(ctl, "ledger_for", lambda _: ledger)
    first = ctl.deploy(output)
    raw = (output / "deployment/record.json").read_bytes()
    before = ledger.snapshot()
    monkeypatch.setattr(ctl, "now", lambda: "2099-01-01T00:00:00+00:00")
    assert ctl.deploy(output) == first
    assert (output / "deployment/record.json").read_bytes() == raw
    assert ledger.snapshot() == before


def test_paid_malformed_membership_retained_and_never_defaulted_or_retried(matrix):
    ledger, _, requests, _, _ = matrix
    request = requests[0]
    client = Client(response('{"states":[],"resolution":"CPU unresolved members","unresolved":""}'))
    artifact = asyncio.run(
        provider.request_once(
            ledger=ledger,
            api_key=KEY,
            request=request,
            client=client,
        )
    )
    row = ledger.request_record(artifact["budget_invocation_id"])
    inspected = provider.paid_record(request, artifact, row)["inspection"]
    assert row["state"] == "SETTLED" and artifact["actual_model_calls"] == 1
    assert not inspected["mapping_admitted"] and inspected["state_by_slot"] == {}
    assert inspected["chi_by_state"] == {} and inspected["errors"]
    assert len(client.calls) == 1 and artifact["retries"] == 0
