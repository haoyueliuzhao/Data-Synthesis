"""CPU orchestration/provenance controls; synthetic retry is not paid-model evidence.

The original four mock-HTTP calls use the existing temporary-wallet fixture.
Permit/activation and the supplementary stage are mocked here; the dedicated
budget/provider suite separately tests their real SQLite/settlement boundaries.
"""

import asyncio
import copy
import json
from types import SimpleNamespace

import httpx
import pytest
from test_finance_v10_production import cohort as cohort
from test_finance_v10_production import run_reviews
from test_finance_v10_production import stopped_history as stopped_history
from test_finance_v10_production import synthetic_parent as synthetic_parent
from test_finance_v10_production import wallet as wallet

from trusted_synthesis.finance_research import v10_final_retry as retry
from trusted_synthesis.finance_research import v10_material as material
from trusted_synthesis.finance_research import v10_production as prod
from trusted_synthesis.finance_research.probe_budget import read_budget_snapshot
from trusted_synthesis.finance_research.v10_review_provider import request_body


@pytest.fixture
def tail(cohort, monkeypatch):
    target = cohort.phase["jobs"][0]
    for name, value in (
        ("EPISODE_ID", target["episode_id"]),
        ("SLOT_ID", target["slot_id"]),
        ("TASK_ID", target["task_id"]),
        ("ROLE", target["role"]),
        ("ORIGIN_INVOCATION_ID", prod.iid_for(cohort.ledger, target)),
    ):
        monkeypatch.setattr(retry, name, value)
    cohort.transport.failures[prod.digest(request_body(cohort.requests[target["episode_id"]]))] = (
        httpx.ReadError("synthetic original missing response")
    )
    completed = run_reviews(cohort)
    directory = retry.supplement_directory(cohort.output)
    permit = prod.bound(dict(schema="synthetic-controller-only-permit", not_paid_evidence=True))
    prod.persist(directory / "authorization", permit)
    state = dict(permit=permit, activation=None, calls=0, result="annotation_failed")
    monkeypatch.setattr(retry, "read_final_retry_permit", lambda _: state["permit"])
    monkeypatch.setattr(
        retry, "read_final_retry_permit_from_connection", lambda *_: state["permit"]
    )
    monkeypatch.setattr(
        retry, "read_final_retry_activation_from_connection", lambda *_: state["activation"]
    )

    def activate(ledger, *, barrier_path):
        barrier = prod.checked(barrier_path)
        assert len(barrier["terminals"]) == len(cohort.phase["jobs"]) == 4
        assert not (cohort.output / "review_seal").exists() or state["activation"] is not None
        if state["activation"] is None:
            state["activation"] = prod.bound(
                dict(
                    permit_id=permit["id"],
                    primary_completion=prod.entry(barrier_path),
                    expected_reviews=4,
                    synthetic_controller_only=True,
                )
            )
        return state["activation"]

    monkeypatch.setattr(retry, "activate_final_retry", activate)

    async def supplementary(output, plan, ledger, context, jobs, **kwargs):
        assert state["activation"] is not None
        assert len(jobs) == 1 and jobs[0]["attempt_index"] == 2
        job = jobs[0]
        path = prod.job_directory(output, job) / "record/record.json"
        if path.exists():
            return {job["episode_id"]: prod.checked(path)}
        state["calls"] += 1
        request = context.request(job)
        assert request == cohort.requests[target["episode_id"]]
        coords = retry.retry_coordinates(ledger.run_id)
        if state["result"] == "network_unknown":
            body = {k: v for k, v in completed[target["episode_id"]].items() if k != "id"}
            body.update(invocation_id=coords["invocation_id"], ack_id="synthetic-second-ack")
        else:
            body = dict(
                schema="v10_paid_process_review.v1",
                **{
                    k: request[k]
                    for k in (
                        "protocol_id",
                        "policy_id",
                        "role",
                        "slot_id",
                        "task_id",
                        "episode_sha256",
                        "view_id",
                    )
                },
                request=request,
                artifact={"budget_invocation_id": coords["invocation_id"]},
                review_status="annotation_failed",
                process_validity="unknown",
                supervision_manifest=None,
                actual_model_call_receipt_verified=True,
                synthetic_not_paid_evidence=True,
            )
        record = prod.bound(body)
        prod.persist(path.parent, record)
        return {job["episode_id"]: record}

    monkeypatch.setattr(prod, "execute_stage", supplementary)
    return SimpleNamespace(
        cohort=cohort, completed=completed, state=state, target=target, directory=directory
    )


def apply(tail, completed=None):
    c = tail.cohort
    return asyncio.run(
        prod.apply_final_retry(
            c.output,
            c.plan,
            c.ledger,
            c.context,
            c.phase,
            tail.completed if completed is None else completed,
        )
    )


def test_no_permit_keeps_original_path_without_extra_attempt(cohort, monkeypatch):
    monkeypatch.setattr(retry, "read_final_retry_permit", lambda _: None)
    completed = {}
    assert asyncio.run(
        prod.apply_final_retry(
            cohort.output, cohort.plan, cohort.ledger, cohort.context, cohort.phase, completed
        )
    ) == (completed, None)
    assert not retry.supplement_directory(cohort.output).exists()
    assert not cohort.transport.calls


def test_three_network_errors_drain_ack_then_stop_without_another_wave(cohort):
    for job in cohort.phase["jobs"][:3]:
        request = cohort.requests[job["episode_id"]]
        cohort.transport.failures[prod.digest(request_body(request))] = httpx.ReadError(
            "synthetic degraded connection wave"
        )
    assert run_reviews(cohort) is None
    assert len(cohort.transport.calls) == 4
    assert len(prod.gather_terminals(cohort.output, cohort.phase["jobs"])) == 4
    state = cohort.ledger.snapshot()
    assert state["pending_requests"] == state["unacknowledged_unknown_requests"] == 0
    assert prod.read_json(cohort.output / "status.json")["phase"] == (
        "V10_REVIEW_NETWORK_SAFETY_SAVED"
    )
    guard = prod.checked(cohort.output / "runtime/network_guard_01/record.json")
    assert guard["same_wave_connection_unknown_threshold"] == 3
    assert not (cohort.output / "review_seal").exists()


def test_whole_primary_matrix_before_retry_and_before_any_joint(tail):
    partial = dict(tail.completed)
    partial.pop(next(iter(partial)))
    with pytest.raises(ValueError, match="all original fixed 2M"):
        apply(tail, partial)
    assert tail.state["calls"] == 0 and tail.state["activation"] is None
    (tail.cohort.output / "joint").mkdir()
    with pytest.raises(ValueError, match="before final qualification"):
        apply(tail)
    assert tail.state["calls"] == 0 and not (tail.directory / "complete_primary_matrix").exists()


def test_exact_original_request_invalid_final_result_and_fixed_logical_denominator(tail):
    c = tail.cohort
    original_path = prod.job_directory(c.output, tail.target) / "record/record.json"
    original_bytes = original_path.read_bytes()
    completed, resolution = apply(tail)
    target = tail.target["episode_id"]
    assert completed[target]["review_status"] == "annotation_failed"
    assert completed[target]["process_validity"] == "unknown"
    assert tail.completed[target]["review_status"] == "network_unknown"
    assert original_path.read_bytes() == original_bytes and tail.state["calls"] == 1
    assert prod.checked(tail.directory / "request/record.json") == c.requests[target]
    seal = prod.complete_review_seal(
        c.output, c.plan, c.phase, completed, retry_resolution=resolution
    )
    assert seal["expected_reviews"] == 4 and seal["physical_attempts"] == 5
    assert seal["returned"] == 4 and seal["network_unknowns"] == 0
    assert seal["retained_original_unknown_attempts"] == 1
    assert tail.target["slot_id"] not in seal["joint_slot_ids"]
    assert seal["terminals"][0]["record"]["path"] == str(tail.directory / "record/record.json")
    assert apply(tail) == (completed, resolution) and tail.state["calls"] == 1
    assert original_path.read_bytes() == original_bytes


def test_second_network_unknown_is_final_without_third_attempt_or_scope_expansion(tail):
    tail.state["result"] = "network_unknown"
    completed, resolution = apply(tail)
    c = tail.cohort
    seal = prod.complete_review_seal(
        c.output, c.plan, c.phase, completed, retry_resolution=resolution
    )
    assert seal["returned"] == 3 and seal["network_unknowns"] == 1
    assert seal["expected_reviews"] == 4 and seal["physical_attempts"] == 5
    assert not prod.read_entry(seal["joint_records"][tail.target["slot_id"]])["joint_valid"]
    assert apply(tail) == (completed, resolution) and tail.state["calls"] == 1
    with pytest.raises(ValueError, match="attempt3"):
        prod.iid_for(c.ledger, {**tail.target, "final_retry": True, "attempt_index": 3})
    with pytest.raises(ValueError, match="another slot"):
        prod.job_directory(c.output, {**c.phase["jobs"][1], "final_retry": True})


def test_material_provenance_binds_real_original_and_synthetic_retry_witness(tail):
    completed, resolution = apply(tail)
    c = tail.cohort
    seal = prod.complete_review_seal(
        c.output, c.plan, c.phase, completed, retry_resolution=resolution
    )
    original = c.ledger.request_record(retry.ORIGIN_INVOCATION_ID)
    second = copy.deepcopy(original)
    coords = retry.retry_coordinates(c.ledger.run_id)
    second.update(
        invocation_id=coords["invocation_id"],
        coordinates_json=json.dumps(coords),
        state="SETTLED",
        evidence_json=json.dumps(
            dict(
                final_retry_permit=tail.state["permit"],
                final_retry_activation=tail.state["activation"],
            )
        ),
    )
    snapshot = read_budget_snapshot(c.ledger.path)
    ledger = SimpleNamespace(
        connection=None,
        config=c.ledger.config,
        run_id=c.ledger.run_id,
        acks={a["invocation_id"]: a for a in snapshot["acknowledged_unknowns"]},
        row=lambda iid: second if iid == coords["invocation_id"] else c.ledger.request_record(iid),
    )
    assert (
        material._final_retry_binding(c.output, c.plan, seal, material.Reader(), ledger)
        == resolution
    )
    # This helper proves provenance only. Full loading still calls the actual
    # validate_review_record, so the explicitly synthetic return is not paid data.
    second["evidence_json"] = json.dumps({"final_retry_permit": {"different": True}})
    with pytest.raises(ValueError, match="real attempt2"):
        material._final_retry_binding(c.output, c.plan, seal, material.Reader(), ledger)
    second["evidence_json"] = json.dumps(
        dict(
            final_retry_permit=tail.state["permit"], final_retry_activation=tail.state["activation"]
        )
    )
    original["reserved_microcny"] += 1
    ledger.row = lambda iid: second if iid == coords["invocation_id"] else original
    with pytest.raises(ValueError, match="exact acknowledged original UNKNOWN"):
        material._final_retry_binding(c.output, c.plan, seal, material.Reader(), ledger)
