"""Six group-scope controls with tiny synthetic matrix/mock HTTP/temp wallets.

Only test coordinates and the original matrix count are monkeypatched. No real
11438-job completion, real authorization registration, API call or verdict is claimed.
"""

# pytest fixture imports intentionally match injected parameter names.
# ruff: noqa: F811

import asyncio
import json

import httpx
import pytest
from test_finance_v10_budget import (  # noqa: F401
    args,
    connection_unknown,
    stopped_history,
    synthetic_parent,
    wallet,
)
from test_finance_v10_funding import apply as apply_funding
from test_finance_v10_production import KEY, cohort  # noqa: F401

from trusted_synthesis.finance_research import v10_final_retry as single
from trusted_synthesis.finance_research import v10_network_retry as group
from trusted_synthesis.finance_research import v10_production as production
from trusted_synthesis.finance_research.contracts import ProviderCallError, digest
from trusted_synthesis.finance_research.probe_budget import BudgetUnavailable, DuplicateInvocation
from trusted_synthesis.finance_research.v10_budget import (
    acknowledge_connection_unknowns,
    map_episode_id,
)
from trusted_synthesis.finance_research.v10_review_protocol import review_record
from trusted_synthesis.finance_research.v10_review_provider import (
    request_body,
    request_review,
    restore_artifact,
)


def send(cohort, request, *, attempt=1, **kwargs):
    return asyncio.run(
        request_review(
            ledger=cohort.ledger,
            api_key=KEY,
            request=request,
            client=cohort.transport,
            attempt_index=attempt,
            **kwargs,
        )
    )


def prepare(cohort, monkeypatch, *, complete=True, register_group=True, funded=False):
    if funded:
        apply_funding(cohort.ledger, cohort.output / "pre-group-funding.sqlite3")
    jobs = cohort.phase["jobs"]
    origin_job = jobs[0]
    origin_request = cohort.requests[origin_job["episode_id"]]
    for name, value in dict(
        ORIGIN_INVOCATION_ID=production.iid_for(cohort.ledger, origin_job),
        EPISODE_ID=origin_job["episode_id"],
        SLOT_ID=origin_job["slot_id"],
        TASK_ID=origin_job["task_id"],
        ORIGINAL_REQUEST_SHA256=digest(request_body(origin_request)),
        PRIMARY_REVIEW_COUNT=4,
    ).items():
        monkeypatch.setattr(single, name, value)
    monkeypatch.setattr(group, "PRIMARY_REVIEW_COUNT", 4)
    # One normal return is intentionally an annotation failure: it is not retry-eligible.
    cohort.transport.responses[digest(request_body(cohort.requests[jobs[1]["episode_id"]]))] = {
        "unrecognized_original": True
    }
    for job in jobs[1:3]:
        request = cohort.requests[job["episode_id"]]
        artifact = send(cohort, request)
        row = cohort.ledger.request_record(artifact["budget_invocation_id"])
        production.publish(
            production.job_directory(cohort.output, job) / "record",
            review_record(request, artifact, row),
        )

    def missing(job):
        request = cohort.requests[job["episode_id"]]
        key = digest(request_body(request))
        cohort.transport.failures[key] = httpx.ReadError("synthetic primary network failure")
        with pytest.raises(ProviderCallError):
            send(cohort, request)
        iid = production.iid_for(cohort.ledger, job)
        receipt = acknowledge_connection_unknowns(
            cohort.ledger, batch_id=cohort.plan["batch_id"], expected_requests={iid: key}
        )
        row = cohort.ledger.request_record(iid)
        production.terminal_record(
            cohort.output, cohort.plan, job, request, row, receipt["records"][0]
        )
        cohort.transport.failures.pop(key)
        return row

    original = missing(origin_job)
    phase_path = cohort.output / "review_registration/record.json"
    old = single.register_final_retry(
        cohort.ledger,
        authorization=single.authorization_definition(),
        primary_registration_path=phase_path,
    )
    permit = None
    if register_group:
        permit = group.register_network_retry(
            cohort.ledger,
            authorization=group.authorization_definition(),
            primary_registration_path=phase_path,
        )
    late = missing(jobs[3]) if complete else None
    terms = []
    for i, job in enumerate(jobs):
        path = production.job_directory(cohort.output, job) / "record/record.json"
        if not path.exists():
            production.publish(
                path.parent, production.bound(dict(negative_control_only_not_terminal=True))
            )
        terms.append(
            dict(
                episode_id=job["episode_id"],
                record=production.entry(path),
                terminal_kind="acknowledged_connection_unknown"
                if i in (0, 3)
                else "paid_model_return",
            )
        )
    body = dict(
        protocol_id=cohort.phase["protocol_id"],
        phase_id=cohort.phase["id"],
        expected_reviews=4,
        terminals=terms,
    )
    barrier = group.supplement_directory(cohort.output) / "complete_primary_matrix/record.json"
    production.publish(
        barrier.parent,
        production.bound(
            dict(schema="v10_primary_review_matrix_complete_before_network_retry.v1", **body)
        ),
    )
    return dict(
        old=old,
        permit=permit,
        original=original,
        late=late,
        barrier=barrier,
        barrier_body=body,
        phase_path=phase_path,
    )


def test_explicit_rule_freezes_all_late_networks_and_preserves_single_once(cohort, monkeypatch):
    assert group.USER_REPLY == "批准上述本批全部网络 UNKNOWN 补发范围"
    assert group.PRIMARY_REVIEW_COUNT == 11438
    setup = prepare(cohort, monkeypatch)
    before = cohort.ledger.snapshot()
    active = group.activate_network_retries(cohort.ledger, barrier_path=setup["barrier"])
    assert active["target_count"] == 2
    assert [t["role"] for t in active["targets"]] == ["A", "B"]
    assert len({t["origin_invocation_id"] for t in active["targets"]}) == 2
    assert (
        sum(t["origin_invocation_id"] == single.ORIGIN_INVOCATION_ID for t in active["targets"])
        == 1
    )
    assert active["superseded_single_permit_id"] == setup["old"]["id"]
    assert single.read_final_retry_permit(cohort.ledger) == setup["old"]
    assert group.activate_network_retries(cohort.ledger, barrier_path=setup["barrier"]) == active
    assert cohort.ledger.snapshot() == before
    assert active["eligibility_uses_financial_verdicts"] is False
    assert all(j["network_retry"] and j["kind"] == "review" for j in active["jobs"])


def test_unactivated_group_overrides_single_and_partial_matrix_cannot_send(cohort, monkeypatch):
    setup = prepare(cohort, monkeypatch, complete=False)
    request = cohort.requests[cohort.phase["jobs"][0]["episode_id"]]
    calls = len(cohort.transport.calls)
    with pytest.raises(BudgetUnavailable, match="freeze the complete"):
        send(cohort, request, attempt=2)
    with pytest.raises(BudgetUnavailable, match="authentic terminal"):
        group.activate_network_retries(cohort.ledger, barrier_path=setup["barrier"])
    assert group.read_network_retry_activation(cohort.ledger) is None
    assert len(cohort.transport.calls) == calls


def test_both_AB_supplements_charge_once_keep_originals_and_restore_same_bytes(cohort, monkeypatch):
    setup = prepare(cohort, monkeypatch, funded=True)
    active = group.activate_network_retries(cohort.ledger, barrier_path=setup["barrier"])
    originals = {
        t["origin_invocation_id"]: cohort.ledger.request_record(t["origin_invocation_id"])
        for t in active["targets"]
    }
    before = cohort.ledger.snapshot()
    for target in active["targets"]:
        request = cohort.requests[target["episode_id"]]
        artifact = send(cohort, request, attempt=2)
        row = cohort.ledger.request_record(artifact["budget_invocation_id"])
        assert row["request_body"] == originals[target["origin_invocation_id"]]["request_body"]
        evidence = json.loads(row["evidence_json"])
        assert evidence["network_retry_permit"] == setup["permit"]
        assert (
            evidence["network_retry_activation"] == active
            and evidence["network_retry_target"] == target
        )
        assert restore_artifact(row, request) == artifact
        calls = len(cohort.transport.calls)
        with pytest.raises(DuplicateInvocation):
            send(cohort, request, attempt=2)
        assert len(cohort.transport.calls) == calls
    after = cohort.ledger.snapshot()
    assert after["requests_reserved"] == before["requests_reserved"] + 2
    assert after["held_microcny"] == before["held_microcny"]
    assert after["effective_hard_cap_microcny"] == 2_000_000_000
    assert after["v10_partition"]["effective_limits"]["review_mapping"]["microcny"] == 1_300_000_000
    assert all(cohort.ledger.request_record(iid) == row for iid, row in originals.items())


def test_normal_returns_mapping_other_queues_and_byte_changes_never_join(cohort, monkeypatch):
    setup = prepare(cohort, monkeypatch)
    mapping = map_episode_id(cohort.plan["batch_id"], cohort.phase["jobs"][0]["task_id"])
    expected = connection_unknown(cohort.ledger, args(cohort.ledger, episode=mapping))
    acknowledge_connection_unknowns(
        cohort.ledger, batch_id=cohort.plan["batch_id"], expected_requests=expected
    )
    active = group.activate_network_retries(cohort.ledger, barrier_path=setup["barrier"])
    assert active["target_count"] == 2  # Excludes 65 historical unknowns and this mapping unknown.
    normal = cohort.requests[cohort.phase["jobs"][1]["episode_id"]]
    calls = len(cohort.transport.calls)
    with pytest.raises(BudgetUnavailable):
        send(cohort, normal, attempt=2)
    target = active["targets"][0]
    request = cohort.requests[target["episode_id"]]
    coords = group.retry_coordinates(cohort.ledger.run_id, target["episode_id"])
    row = cohort.ledger.request_record(target["origin_invocation_id"])
    with pytest.raises(BudgetUnavailable, match="HTTP bytes"):
        cohort.ledger.reserve(
            coords["invocation_id"],
            coordinates=coords,
            request=request_body(request),
            request_body=row["request_body"] + b" ",
        )
    with pytest.raises(ValueError):
        send(cohort, request, attempt=3)
    other_coords = group.retry_coordinates(cohort.ledger.run_id, mapping)
    with pytest.raises(BudgetUnavailable):
        cohort.ledger.reserve(
            other_coords["invocation_id"],
            coordinates=other_coords,
            request=json.loads(row["request_body"]),
            request_body=row["request_body"],
        )
    assert len(cohort.transport.calls) == calls


def test_supplementary_unknown_retains_new_hold_without_expanding_frozen_group(cohort, monkeypatch):
    setup = prepare(cohort, monkeypatch)
    active = group.activate_network_retries(cohort.ledger, barrier_path=setup["barrier"])
    target = active["targets"][0]
    request = cohort.requests[target["episode_id"]]
    key = digest(request_body(request))
    cohort.transport.failures[key] = httpx.ReadError("synthetic supplementary missing response")
    before = cohort.ledger.snapshot()
    with pytest.raises(ProviderCallError):
        send(cohort, request, attempt=2)
    receipt = acknowledge_connection_unknowns(
        cohort.ledger,
        batch_id=cohort.plan["batch_id"],
        expected_requests={target["retry_invocation_id"]: key},
    )
    assert receipt["records"][0]["model_response"] is None
    assert (
        cohort.ledger.snapshot()["held_microcny"]
        == before["held_microcny"] + target["origin_reserved_microcny"]
    )
    assert group.read_network_retry_activation(cohort.ledger) == active
    calls = len(cohort.transport.calls)
    with pytest.raises(DuplicateInvocation):
        send(cohort, request, attempt=2)
    with pytest.raises(ValueError):
        send(cohort, request, attempt=3)
    assert len(cohort.transport.calls) == calls


def test_existing_single_activation_or_send_blocks_group_replacement(cohort, monkeypatch):
    setup = prepare(cohort, monkeypatch, register_group=False)
    path = single.supplement_directory(cohort.output) / "complete_primary_matrix/record.json"
    production.publish(
        path.parent,
        production.bound(
            dict(
                schema="v10_primary_review_matrix_complete_before_final_retry.v1",
                **setup["barrier_body"],
            )
        ),
    )
    single.activate_final_retry(cohort.ledger, barrier_path=path)
    with pytest.raises(BudgetUnavailable, match="activated/sent"):
        group.register_network_retry(
            cohort.ledger,
            authorization=group.authorization_definition(),
            primary_registration_path=setup["phase_path"],
        )
    # No group permit exists: legacy already-authorized exact path still works.
    artifact = send(cohort, cohort.requests[single.EPISODE_ID], attempt=2)
    assert artifact["budget_coordinates"]["attempt_index"] == 2
    with pytest.raises(BudgetUnavailable, match="activated/sent"):
        group.register_network_retry(
            cohort.ledger,
            authorization=group.authorization_definition(),
            primary_registration_path=setup["phase_path"],
        )
    assert group.read_network_retry_permit(cohort.ledger) is None
