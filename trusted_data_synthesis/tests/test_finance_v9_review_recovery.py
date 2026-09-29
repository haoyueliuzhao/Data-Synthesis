"""Temporary paid-ledger fixtures, mocked HTTP, exact-original recovery only."""

import copy
import json
from types import SimpleNamespace

import pytest
from test_finance_research_probe_provider import Client
from test_finance_v6_strict_review_provider import call, ledger_fixture, response_fixture
from test_finance_v8_single_target_review import authored, fixture

from trusted_synthesis.finance_research import v9_review_recovery as recovery
from trusted_synthesis.finance_research.calibration import publish
from trusted_synthesis.finance_research.v6_decomposed_review import job_directory


def setup(tmp_path):
    ledger = ledger_fixture(tmp_path)
    _, _, requests, _, _ = fixture()
    request = requests[0]["s0"]
    request.update(max_output_tokens=16384, capacity_policy_id="synthetic-frozen")
    jobs = [
        dict(key="slot0", stage="slot", task_id="t", slot_id="s0", reviewer=0),
        dict(key="slot1", stage="slot", task_id="t", slot_id="s1", reviewer=0),
    ]
    plan = dict(
        id="synthetic-production",
        budget_config=dict(run_id=ledger.run_id),
        budget_database=str(ledger.path),
        jobs=jobs,
    )
    coords = recovery.coordinates(plan, jobs[0])
    client = Client(response_fixture(json.dumps(authored(request))))
    artifact = call(ledger, client, request, episode_id=coords["episode_id"])
    return ledger, plan, jobs, request, artifact, client


def test_reconstruct_settled_original_bytes_without_second_model_or_wallet_write(tmp_path):
    ledger, plan, jobs, request, artifact, client = setup(tmp_path)
    before = ledger.snapshot()
    result = recovery.restore_settled_artifact(ledger, artifact["budget_invocation_id"], request)
    for key, value in artifact.items():
        assert result[key] == value
    assert result["recovered_from_exact_original_ledger_bytes"]
    assert result["new_model_calls_during_recovery"] == 0
    assert len(client.calls) == 1 and ledger.snapshot() == before
    changed = copy.deepcopy(request)
    changed["max_output_tokens"] = 32768
    with pytest.raises(ValueError, match="bytes differ"):
        recovery.restore_settled_artifact(ledger, artifact["budget_invocation_id"], changed)


def test_recovery_reuses_return_rebuilds_only_missing_local_check_and_identifies_unsent(
    tmp_path, monkeypatch
):
    ledger, plan, jobs, request, artifact, client = setup(tmp_path)
    iid = artifact["budget_invocation_id"]
    row = ledger.request_record(iid)
    monkeypatch.setattr(recovery, "production_rows", lambda path: {iid: row})
    context = SimpleNamespace(request=lambda job: request)
    output = tmp_path / "production"
    publish(job_directory(output, jobs[0]) / "response", artifact)
    before = ledger.snapshot()
    audit, completed, _ = recovery.inspect_recovery(output, plan, ledger, context)
    assert not audit["resume_admitted"] and completed == {}
    assert not (job_directory(output, jobs[0]) / "assessment").exists()
    audit, completed, totals = recovery.inspect_recovery(
        output, plan, ledger, context, repair_local=True
    )
    assert audit["resume_admitted"] and list(completed) == ["slot0"]
    assert audit["confirmed_unsent_jobs"] == ["slot1"]
    assert audit["local_actions"][0]["action"] == "apply_original_frozen_checker"
    assert totals["cost_microcny"] == artifact["peak_tariff_upper_bound_microcny"]
    assert ledger.snapshot() == before and len(client.calls) == 1
    again, reused, _ = recovery.inspect_recovery(output, plan, ledger, context, repair_local=True)
    assert again["resume_admitted"] and not again["local_actions"] and reused == completed


def test_missing_local_response_reconstructed_from_original_settled_sqlite(tmp_path, monkeypatch):
    ledger, plan, jobs, request, artifact, client = setup(tmp_path)
    iid = artifact["budget_invocation_id"]
    monkeypatch.setattr(recovery, "production_rows", lambda path: {iid: ledger.request_record(iid)})
    audit, completed, _ = recovery.inspect_recovery(
        tmp_path / "out",
        plan,
        ledger,
        SimpleNamespace(request=lambda job: request),
        repair_local=True,
    )
    assert audit["resume_admitted"] and list(completed) == ["slot0"]
    assert [a["action"] for a in audit["local_actions"]] == [
        "restore_original_ledger_response",
        "apply_original_frozen_checker",
    ]
    assert len(client.calls) == 1


@pytest.mark.parametrize("state", ["RESERVED", "DISPATCHED", "UNKNOWN"])
def test_existing_nonsettled_call_never_marked_unsent_or_resent(tmp_path, monkeypatch, state):
    ledger, plan, jobs, request, artifact, client = setup(tmp_path)
    iid = artifact["budget_invocation_id"]
    row = {**ledger.request_record(iid), "state": state}
    monkeypatch.setattr(recovery, "production_rows", lambda path: {iid: row})
    audit, completed, _ = recovery.inspect_recovery(
        tmp_path / "out",
        plan,
        ledger,
        SimpleNamespace(request=lambda job: request),
        repair_local=True,
    )
    assert not audit["resume_admitted"] and completed == {}
    assert audit["confirmed_unsent_jobs"] == ["slot1"]
    assert audit["blocker_records"][0]["ledger_state"] == state
    assert len(client.calls) == 1


def test_foreign_matrix_row_cannot_be_spliced(tmp_path, monkeypatch):
    ledger, plan, jobs, request, artifact, _ = setup(tmp_path)
    monkeypatch.setattr(recovery, "production_rows", lambda path: {"another-protocol-id": {}})
    with pytest.raises(ValueError, match="foreign production"):
        recovery.inspect_recovery(
            tmp_path / "out", plan, ledger, SimpleNamespace(request=lambda job: request)
        )
