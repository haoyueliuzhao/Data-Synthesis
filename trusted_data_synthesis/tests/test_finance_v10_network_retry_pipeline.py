"""Group-tail CPU boundaries; synthetic supplementary records are NOT paid evidence.

Original four calls use mock HTTP with the existing temporary wallet. The group
permit, activation and new calls are mocked; budget/provider tests exercise the
real authorization and settlement gates independently.
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

from trusted_synthesis.finance_research import v10_material as material
from trusted_synthesis.finance_research import v10_network_retry as retry
from trusted_synthesis.finance_research import v10_production as prod
from trusted_synthesis.finance_research.probe_budget import (
    _request_record_digest,
    read_budget_snapshot,
)
from trusted_synthesis.finance_research.v10_review_provider import request_body


@pytest.fixture
def group(cohort, monkeypatch):
    chosen = [cohort.phase["jobs"][0], cohort.phase["jobs"][-1]]
    for job in chosen:
        request = cohort.requests[job["episode_id"]]
        cohort.transport.failures[prod.digest(request_body(request))] = httpx.ReadError(
            "synthetic original connection interruption"
        )
    completed = run_reviews(cohort)
    directory = retry.supplement_directory(cohort.output)
    old_single = prod.bound(dict(schema="synthetic-old-single-permit", original_preserved=True))
    prod.persist(cohort.output / "final_retry_01/authorization", old_single)
    permit = prod.bound(
        dict(
            schema="synthetic-group-permit",
            superseded_single_permit_id=old_single["id"],
            synthetic_not_production_authorization=True,
        )
    )
    prod.persist(directory / "authorization", permit)
    state = dict(
        permit=permit,
        activation=None,
        sent=[],
        add_returned=False,
        stop_after=None,
        rows={},
        acks={
            r["invocation_id"]: r
            for r in read_budget_snapshot(cohort.ledger.path)["acknowledged_unknowns"]
        },
    )
    monkeypatch.setattr(retry, "read_network_retry_permit", lambda _: permit)
    monkeypatch.setattr(retry, "read_network_retry_permit_from_connection", lambda *_: permit)
    monkeypatch.setattr(
        retry, "read_network_retry_activation_from_connection", lambda *_: state["activation"]
    )

    def activate(ledger, *, barrier_path):
        barrier = prod.checked(barrier_path)
        assert len(barrier["terminals"]) == 4
        if state["activation"] is not None:
            assert state["activation"]["primary_completion"] == prod.entry(barrier_path)
            return state["activation"]
        selected = chosen + ([cohort.phase["jobs"][1]] if state["add_returned"] else [])
        targets = []
        for job in selected:
            row = ledger.request_record(prod.iid_for(ledger, job))
            targets.append(
                dict(
                    **{k: job[k] for k in ("episode_id", "slot_id", "task_id", "role")},
                    origin_invocation_id=row["invocation_id"],
                    original_request_sha256=row["request_sha256"],
                    origin_reserved_microcny=row["reserved_microcny"],
                    retry_invocation_id=retry.retry_coordinates(ledger.run_id, job["episode_id"])[
                        "invocation_id"
                    ],
                )
            )
        state["activation"] = prod.bound(
            dict(
                schema="v10_network_retry_activation.v1",
                permit_id=permit["id"],
                primary_registration=prod.entry(cohort.output / "review_registration/record.json"),
                primary_completion=prod.entry(barrier_path),
                expected_reviews=4,
                all_primary_attempt1_terminal=True,
                target_count=len(targets),
                targets=targets,
                jobs=[
                    dict(
                        kind="review",
                        network_retry=True,
                        **{
                            k: t[k]
                            for k in (
                                "episode_id",
                                "slot_id",
                                "task_id",
                                "role",
                                "origin_invocation_id",
                            )
                        },
                    )
                    for t in targets
                ],
                superseded_single_permit_id=old_single["id"],
            )
        )
        return state["activation"]

    monkeypatch.setattr(retry, "activate_network_retries", activate)

    async def single_must_not_run(*args, **kwargs):
        pytest.fail("group authority must subsume rather than duplicate the prior single item")

    monkeypatch.setattr(prod, "apply_final_retry", single_must_not_run)

    async def supplementary(output, plan, ledger, context, jobs, **kwargs):
        assert jobs == state["activation"]["jobs"]
        results = {}
        for index, job in enumerate(jobs):
            path = prod.job_directory(output, job) / "record/record.json"
            if path.exists():
                results[job["episode_id"]] = prod.checked(path)
                continue
            if state["stop_after"] is not None and len(state["sent"]) >= state["stop_after"]:
                return None
            request = context.request(job)
            assert request == cohort.requests[job["episode_id"]]
            target = state["activation"]["targets"][index]
            coords = retry.retry_coordinates(ledger.run_id, job["episode_id"])
            row = copy.deepcopy(ledger.request_record(target["origin_invocation_id"]))
            row.update(
                invocation_id=coords["invocation_id"],
                coordinates_json=json.dumps(coords),
                state="SETTLED" if index == 0 else "UNKNOWN",
                evidence_json=json.dumps(
                    dict(
                        network_retry_permit=permit,
                        network_retry_activation=state["activation"],
                        network_retry_target=target,
                    )
                ),
            )
            if index == 0:
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
            else:
                body = {k: v for k, v in completed[job["episode_id"]].items() if k != "id"}
                ack = dict(
                    invocation_id=coords["invocation_id"],
                    original_unknown_record_sha256=_request_record_digest(row),
                    id="synthetic-attempt2-ack",
                )
                state["acks"][coords["invocation_id"]] = ack
                body.update(invocation_id=coords["invocation_id"], ack_id=ack["id"])
            state["rows"][coords["invocation_id"]] = row
            record = prod.bound(body)
            prod.persist(path.parent, record)
            state["sent"].append(coords["invocation_id"])
            results[job["episode_id"]] = record
        return results

    monkeypatch.setattr(prod, "execute_stage", supplementary)
    return SimpleNamespace(
        cohort=cohort, completed=completed, state=state, directory=directory, chosen=chosen
    )


def apply(group, completed=None):
    c = group.cohort
    return asyncio.run(
        prod.apply_registered_retries(
            c.output,
            c.plan,
            c.ledger,
            c.context,
            c.phase,
            group.completed if completed is None else completed,
        )
    )


@pytest.mark.parametrize("case", ["prefix", "returned_item"])
def test_group_requires_whole_primary_and_never_includes_returned_items(group, case):
    completed = dict(group.completed)
    if case == "prefix":
        completed.pop(next(iter(completed)))
        error = "all original fixed 2M"
    else:
        group.state["add_returned"] = True
        error = "every and only primary network UNKNOWN"
    with pytest.raises(ValueError, match=error):
        apply(group, completed)
    assert group.state["sent"] == []
    assert not (group.directory / "resolution").exists()


def test_group_resume_unique_attempt2_keeps_old_single_and_primary_bytes(group):
    c = group.cohort
    old_paths = [prod.job_directory(c.output, j) / "record/record.json" for j in c.phase["jobs"]]
    old_paths += [
        c.output / "final_retry_01/authorization/record.json",
        c.output / "runtime/network_guard_01/record.json",
    ]
    old_bytes = {p: p.read_bytes() for p in old_paths}
    group.state["stop_after"] = 1
    assert apply(group) is None and len(group.state["sent"]) == 1
    assert not (c.output / "review_seal").exists() and not (group.directory / "resolution").exists()
    group.state["stop_after"] = None
    effective, options = apply(group)
    assert set(options) == {"network_retry_resolution"}
    assert len(group.state["sent"]) == len(set(group.state["sent"])) == 2
    seal = prod.complete_review_seal(c.output, c.plan, c.phase, effective, **options)
    assert seal["expected_reviews"] == 4 and seal["physical_attempts"] == 6
    assert seal["primary_first_pass_returns"] == seal["primary_first_pass_network_unknowns"] == 2
    assert seal["retry_returns"] == seal["retry_network_unknowns"] == 1
    assert seal["returned"] == 3 and seal["network_unknowns"] == 1
    assert seal["retained_original_unknown_attempts"] == 2
    assert seal["joint_slot_ids"] == []  # Invalid and UNKNOWN are retained, not cherry-picked.
    assert apply(group) == (effective, options) and len(group.state["sent"]) == 2
    prod.register_network_guard(c.output, c.plan, network_retry=True)
    assert {p: p.read_bytes() for p in old_paths} == old_bytes
    assert not (c.output / "final_retry_01/activation").exists()
    for job in group.state["activation"]["jobs"]:
        with pytest.raises(ValueError, match="attempt3"):
            prod.iid_for(c.ledger, {**job, "attempt_index": 3})
        with pytest.raises(ValueError, match="mapping"):
            prod.job_directory(c.output, {**job, "kind": "mapping"})


def test_material_group_provenance_checks_manifest_target_witness_and_denominators(group):
    effective, options = apply(group)
    c = group.cohort
    seal = prod.complete_review_seal(c.output, c.plan, c.phase, effective, **options)
    ledger = SimpleNamespace(
        connection=None,
        config=c.ledger.config,
        run_id=c.ledger.run_id,
        acks=group.state["acks"],
        row=lambda iid: group.state["rows"].get(iid) or c.ledger.request_record(iid),
    )
    replacements = material._network_retry_binding(
        c.output, c.plan, seal, material.Reader(), ledger
    )
    assert list(replacements) == [j["episode_id"] for j in group.chosen]
    broken = copy.deepcopy(seal)
    broken["physical_attempts"] -= 1
    with pytest.raises(ValueError, match="physical retained holds"):
        material._network_retry_binding(c.output, c.plan, broken, material.Reader(), ledger)
    iid = group.state["sent"][0]
    group.state["rows"][iid]["evidence_json"] = json.dumps(
        {"network_retry_target": {"wrong": True}}
    )
    with pytest.raises(ValueError, match="wallet group witnesses"):
        material._network_retry_binding(c.output, c.plan, seal, material.Reader(), ledger)
