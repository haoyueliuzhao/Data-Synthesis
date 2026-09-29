"""One-off retry controls; tiny synthetic matrix, mock HTTP, temporary wallets only.

The production constants stay fixed. Tests explicitly monkeypatch only those
coordinates/counts to exercise the same real ledger with a four-job CPU fixture;
they are not records of the real authorized paid request or its completion.
"""

# Imported pytest fixtures intentionally share the names of injected parameters.
# ruff: noqa: F811

import asyncio
import copy
import json

import httpx
import pytest
from test_finance_v10_budget import stopped_history, synthetic_parent, wallet  # noqa: F401
from test_finance_v10_funding import apply as apply_funding
from test_finance_v10_production import KEY, cohort  # noqa: F401

from trusted_synthesis.finance_research import v10_final_retry as retry
from trusted_synthesis.finance_research import v10_production as production
from trusted_synthesis.finance_research.contracts import (
    ProviderCallError,
    digest,
)
from trusted_synthesis.finance_research.probe_budget import BudgetUnavailable, DuplicateInvocation
from trusted_synthesis.finance_research.providers import _json
from trusted_synthesis.finance_research.v10_budget import acknowledge_connection_unknowns
from trusted_synthesis.finance_research.v10_review_protocol import review_record
from trusted_synthesis.finance_research.v10_review_provider import (
    request_body,
    request_review,
    restore_artifact,
    validate_paid_artifact,
)


def setup_permit(cohort, monkeypatch, *, complete=True, funded=False):
    if funded:
        apply_funding(cohort.ledger, cohort.output / "pre-retry-funding.sqlite3")
    jobs = cohort.phase["jobs"]
    job, request = jobs[0], cohort.requests[jobs[0]["episode_id"]]
    origin = production.iid_for(cohort.ledger, job)
    for key, value in dict(
        ORIGIN_INVOCATION_ID=origin,
        EPISODE_ID=job["episode_id"],
        SLOT_ID=job["slot_id"],
        TASK_ID=job["task_id"],
        ORIGINAL_REQUEST_SHA256=digest(request_body(request)),
        PRIMARY_REVIEW_COUNT=4,
    ).items():
        monkeypatch.setattr(retry, key, value)
    for other in jobs[1:] if complete else jobs[1:-1]:
        req = cohort.requests[other["episode_id"]]
        artifact = asyncio.run(
            request_review(ledger=cohort.ledger, api_key=KEY, request=req, client=cohort.transport)
        )
        row = cohort.ledger.request_record(artifact["budget_invocation_id"])
        production.publish(
            production.job_directory(cohort.output, other) / "record",
            review_record(req, artifact, row),
        )
    key = digest(request_body(request))
    cohort.transport.failures[key] = httpx.ReadError("synthetic original missing reply")
    with pytest.raises(ProviderCallError):
        asyncio.run(
            request_review(
                ledger=cohort.ledger, api_key=KEY, request=request, client=cohort.transport
            )
        )
    receipt = acknowledge_connection_unknowns(
        cohort.ledger, batch_id=cohort.plan["batch_id"], expected_requests={origin: key}
    )
    original = cohort.ledger.request_record(origin)
    production.terminal_record(
        cohort.output, cohort.plan, job, request, original, receipt["records"][0]
    )
    cohort.transport.failures.pop(key)
    permit = retry.register_final_retry(
        cohort.ledger,
        authorization=retry.authorization_definition(),
        primary_registration_path=cohort.output / "review_registration/record.json",
    )
    production.publish(retry.supplement_directory(cohort.output) / "authorization", permit)
    terms = []
    for item in jobs:
        path = production.job_directory(cohort.output, item) / "record/record.json"
        if not path.exists():
            production.publish(
                path.parent, production.bound(dict(negative_control_not_a_real_terminal=True))
            )
        terms.append(
            dict(
                episode_id=item["episode_id"],
                record=production.entry(path),
                terminal_kind="acknowledged_connection_unknown"
                if item == job
                else "paid_model_return",
            )
        )
    barrier = production.bound(
        dict(
            schema="v10_primary_review_matrix_complete_before_final_retry.v1",
            protocol_id=cohort.phase["protocol_id"],
            phase_id=cohort.phase["id"],
            expected_reviews=4,
            terminals=terms,
        )
    )
    path = retry.supplement_directory(cohort.output) / "complete_primary_matrix/record.json"
    production.publish(path.parent, barrier)
    return request, original, permit, path


def supplement(cohort, request, **kwargs):
    return asyncio.run(
        request_review(
            ledger=cohort.ledger,
            api_key=KEY,
            request=request,
            client=cohort.transport,
            attempt_index=2,
            **kwargs,
        )
    )


def test_real_whitelist_constants_and_unregistered_attempt2_rejected(cohort):
    assert (
        retry.ORIGIN_INVOCATION_ID
        == "invocation:90d0508e9d9354283eddc62b377a36ceeefc525ea54644fa6bf98dc1e617aa82"
    )
    assert (
        retry.EPISODE_ID
        == "v10review:689a196d84b61eadcfb607013a8ecfd72dfb01ebaaa972453d38f109126942c3"
    )
    assert retry.TASK_ID == "C/2009/page_141.pdf-2" and retry.ROLE == "A"
    assert retry.PRIMARY_REVIEW_COUNT == 11438
    assert retry.read_final_retry_permit(cohort.ledger) is None
    request = next(iter(cohort.requests.values()))
    before = cohort.ledger.snapshot()
    with pytest.raises(BudgetUnavailable):
        supplement(cohort, request)
    assert not cohort.transport.calls and cohort.ledger.snapshot() == before


def test_registration_never_allows_half_matrix_or_unactivated_send(cohort, monkeypatch):
    request, _, _, barrier = setup_permit(cohort, monkeypatch, complete=False)
    before = len(cohort.transport.calls)
    with pytest.raises(BudgetUnavailable):
        supplement(cohort, request)
    with pytest.raises(BudgetUnavailable, match="lacks its real"):
        retry.activate_final_retry(cohort.ledger, barrier_path=barrier)
    with pytest.raises(BudgetUnavailable):
        supplement(cohort, request)
    assert len(cohort.transport.calls) == before
    assert (
        cohort.ledger.request_record(retry.retry_coordinates(cohort.ledger.run_id)["invocation_id"])
        is None
    )


def test_exact_last_return_adds_one_charge_keeps_original_and_restores_without_resend(
    cohort, monkeypatch
):
    request, original, permit, barrier = setup_permit(cohort, monkeypatch, funded=True)
    activation = retry.activate_final_retry(cohort.ledger, barrier_path=barrier)
    assert retry.activate_final_retry(cohort.ledger, barrier_path=barrier) == activation
    before = cohort.ledger.snapshot()
    artifact = supplement(cohort, request)
    row = cohort.ledger.request_record(artifact["budget_invocation_id"])
    after = cohort.ledger.snapshot()
    assert json.loads(row["coordinates_json"])["attempt_index"] == 2
    assert row["request_body"] == original["request_body"]
    assert cohort.ledger.request_record(retry.ORIGIN_INVOCATION_ID) == original
    assert after["requests_reserved"] == before["requests_reserved"] + 1
    assert after["held_microcny"] == before["held_microcny"]
    assert after["effective_hard_cap_microcny"] == 2_000_000_000
    assert after["v10_partition"]["effective_limits"]["review_mapping"]["microcny"] == 1_300_000_000
    evidence = json.loads(row["evidence_json"])
    assert (
        evidence["final_retry_permit"] == permit
        and evidence["final_retry_activation"] == activation
    )
    calls = len(cohort.transport.calls)
    assert restore_artifact(row, request) == artifact
    assert validate_paid_artifact(request, artifact, row)["actual_response_and_usage_bound"]
    with pytest.raises(DuplicateInvocation):
        supplement(cohort, request)
    assert len(cohort.transport.calls) == calls
    assert retry.read_final_retry_permit(cohort.ledger) == permit


def test_no_other_slot_attempt3_or_byte_variation_can_use_permit(cohort, monkeypatch):
    request, original, _, barrier = setup_permit(cohort, monkeypatch)
    retry.activate_final_retry(cohort.ledger, barrier_path=barrier)
    other = list(cohort.requests.values())[1]
    before = len(cohort.transport.calls)
    with pytest.raises(BudgetUnavailable):
        supplement(cohort, other)
    with pytest.raises(ValueError):
        asyncio.run(
            request_review(
                ledger=cohort.ledger,
                api_key=KEY,
                request=request,
                client=cohort.transport,
                attempt_index=3,
            )
        )
    coords = retry.retry_coordinates(cohort.ledger.run_id)
    body = request_body(request)
    with pytest.raises(BudgetUnavailable, match="HTTP bytes"):
        cohort.ledger.reserve(
            coords["invocation_id"],
            coordinates=coords,
            request=body,
            request_body=original["request_body"] + b" ",
        )
    assert len(cohort.transport.calls) == before
    assert cohort.ledger.request_record(coords["invocation_id"]) is None


def test_second_connection_unknown_retains_both_holds_and_never_authorizes_third(
    cohort, monkeypatch
):
    request, original, _, barrier = setup_permit(cohort, monkeypatch)
    retry.activate_final_retry(cohort.ledger, barrier_path=barrier)
    before = cohort.ledger.snapshot()
    key = digest(request_body(request))
    cohort.transport.failures[key] = httpx.ReadError("synthetic final missing reply")
    with pytest.raises(ProviderCallError):
        supplement(cohort, request)
    iid = retry.retry_coordinates(cohort.ledger.run_id)["invocation_id"]
    receipt = acknowledge_connection_unknowns(
        cohort.ledger, batch_id=cohort.plan["batch_id"], expected_requests={iid: key}
    )
    after = cohort.ledger.snapshot()
    assert after["held_microcny"] == before["held_microcny"] + 2_113_536
    assert cohort.ledger.request_record(retry.ORIGIN_INVOCATION_ID) == original
    assert receipt["records"][0]["model_response"] is None
    calls = len(cohort.transport.calls)
    with pytest.raises(DuplicateInvocation):
        supplement(cohort, request)
    assert len(cohort.transport.calls) == calls


def test_confirmed_unsent_supplement_reuses_original_reservation_once(cohort, monkeypatch):
    request, original, _, barrier = setup_permit(cohort, monkeypatch)
    retry.activate_final_retry(cohort.ledger, barrier_path=barrier)
    coords = retry.retry_coordinates(cohort.ledger.run_id)
    body = request_body(request)
    cohort.ledger.reserve(
        coords["invocation_id"], coordinates=coords, request=body, request_body=_json(body).encode()
    )
    before = cohort.ledger.snapshot()
    artifact = supplement(cohort, request, resume_reserved=True)
    assert artifact["budget_coordinates"] == coords
    assert cohort.ledger.snapshot()["requests_reserved"] == before["requests_reserved"]
    assert cohort.ledger.request_record(retry.ORIGIN_INVOCATION_ID) == original
    changed = copy.deepcopy(cohort.ledger.request_record(coords["invocation_id"]))
    evidence = json.loads(changed["evidence_json"])
    evidence["final_retry_activation"]["expected_reviews"] = 3
    changed["evidence_json"] = json.dumps(evidence)
    with pytest.raises(BudgetUnavailable):
        restore_artifact(changed, request)
