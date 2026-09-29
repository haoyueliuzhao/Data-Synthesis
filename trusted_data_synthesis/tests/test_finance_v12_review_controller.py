"""Controller-only synthetic files and in-memory ledger; no HTTP/SQLite/GPU work."""

import asyncio
import copy
import json
from types import SimpleNamespace

import pytest

from trusted_synthesis.finance_research import v12_review_controller as ctl
from trusted_synthesis.finance_research.contracts import ProviderCallError, invocation_identity
from trusted_synthesis.finance_research.probe_budget import (
    BudgetUnavailable,
    _request_record_digest,
)


class MemoryLedger:
    run_id = "synthetic-memory-wallet"

    def __init__(self, capacity):
        self.capacity, self.rows, self.acks, self.halt = capacity, {}, {}, None

    def request_record(self, iid):
        return copy.deepcopy(self.rows.get(iid))

    def snapshot(self):
        pending = sum(r["state"] in {"RESERVED", "DISPATCHED"} for r in self.rows.values())
        held = sum(r["reserved_microcny"] for r in self.rows.values() if r["state"] != "SETTLED")
        return dict(
            pending_requests=pending,
            halt=self.halt,
            exposure_microcny=held,
            unacknowledged_unknown_requests=sum(
                r["state"] == "UNKNOWN" and iid not in self.acks for iid, r in self.rows.items()
            ),
        )


class MemoryProvider:
    def __init__(self):
        self.calls, self.resume_flags, self.failures, self.overrides = [], [], {}, {}
        self.active = self.maximum = 0

    def annotation_client(self, **kwargs):
        assert kwargs["proxy"] == "http://127.0.0.1:7897"
        return self

    async def __aenter__(self):
        return self

    async def __aexit__(self, *args):
        return False

    async def request_once(self, *, ledger, request, resume_reserved, **kwargs):
        coords = invocation_identity(
            dict(run_id=ledger.run_id, episode_id=request["episode_id"], attempt_index=1),
            turn_index=0,
        )
        iid = coords["invocation_id"]
        row = ledger.rows.get(iid)
        if row is None:
            if ledger.snapshot()["pending_requests"] >= ledger.capacity:
                raise BudgetUnavailable("temporary full reservation capacity")
            row = dict(
                invocation_id=iid,
                state="RESERVED",
                dispatched_at=None,
                reserved_microcny=100,
                request_sha256=ctl.digest(request),
                response_body=None,
                http_status=None,
                usage_json=None,
                settled_microcny=None,
                evidence_json=None,
            )
            ledger.rows[iid] = row
            assert not resume_reserved
        else:
            assert row["state"] == "RESERVED" and resume_reserved
        row.update(state="DISPATCHED", dispatched_at=1)
        self.calls.append(iid)
        self.resume_flags.append(resume_reserved)
        self.active += 1
        self.maximum = max(self.maximum, self.active)
        await asyncio.sleep(0.001)
        self.active -= 1
        failure = self.failures.get(request["episode_id"])
        if failure:
            network = failure == "network"
            evidence = (
                dict(exception_type="ReadError", service_response_received=False) if network else {}
            )
            row.update(
                state="UNKNOWN",
                evidence_json=json.dumps(evidence),
                response_body=None if network else b"service error",
                http_status=None if network else 429,
            )
            ledger.halt = iid
            raise ProviderCallError(
                "synthetic network" if network else "HTTP429",
                settlement="unknown",
                actual_model_calls=1,
                evidence=evidence,
            )
        artifact = ctl.bound(dict(schema="synthetic_V12_artifact", budget_invocation_id=iid))
        row.update(state="SETTLED", settled_microcny=1, artifact=artifact)
        return artifact

    def restore_settled(self, row, request):
        assert row["state"] == "SETTLED"
        return row["artifact"]

    def paid_record(self, request, artifact, row):
        assert row["state"] == "SETTLED" and row["artifact"] == artifact
        outcomes = dict(
            process_validity="valid",
            process_candidate_usable=True,
            projection_usable=True if request["role"] == "A" else None,
            failure_codes=[],
            envelope_complete=True,
            raw_JSON_complete=True,
        )
        outcomes.update(self.overrides.get(request["episode_id"], {}))
        inspection = dict(
            actual_model_call_receipt_verified=False,
            training_admissibility={"production_admitted": False},
            reason_projection=dict(
                raw_public_characters=12,
                positive_public_characters=0,
                all_public_reasoning_masked=True,
            ),
            synthetic_not_a_real_V11_judgment=True,
        )
        return ctl.bound(
            dict(
                schema="v12_paid_process_review.v1",
                request=request,
                artifact=artifact,
                actual_model_call_receipt_verified=True,
                inspection=inspection,
                new_pipeline_outcomes=outcomes,
                role=request["role"],
                slot_id=request["slot_id"],
                task_id=request["task_id"],
                protocol_id="synthetic-protocol",
            )
        )


class MemoryBudget:
    NETWORK_EXCEPTIONS = {"ReadError"}

    @staticmethod
    def acknowledge_connection_unknowns(ledger, *, protocol_id, expected_requests):
        assert ledger.snapshot()["pending_requests"] == 0
        records = []
        for iid, request_sha in expected_requests.items():
            row = ledger.rows[iid]
            assert row["request_sha256"] == request_sha and ctl._network_candidate(row)
            if iid not in ledger.acks:
                ledger.acks[iid] = ctl.bound(
                    dict(
                        invocation_id=iid,
                        expected_request_sha256=request_sha,
                        original_unknown_record_sha256=_request_record_digest(row),
                    )
                )
            records.append(ledger.acks[iid])
        if ledger.halt in expected_requests:
            ledger.halt = None
        return ctl.bound(dict(protocol_id=protocol_id, records=records))


@pytest.fixture
def setup(tmp_path, monkeypatch):
    provider = MemoryProvider()
    monkeypatch.setattr(ctl, "_provider", lambda: provider)
    monkeypatch.setattr(ctl, "_budget", lambda: MemoryBudget)
    monkeypatch.setattr(ctl, "_protocol", lambda: SimpleNamespace(request_body=lambda r: r))
    monkeypatch.setattr(ctl, "explicit_proxy", lambda plan: "http://127.0.0.1:7897")

    def build(count=4, capacity=64):
        assert count % 2 == 0
        jobs, requests = [], {}
        for i in range(count):
            role = "A" if i % 2 == 0 else "B"
            slot = "v10gen:" + ctl.digest(i // 2)
            eid = "v12review:" + ctl.digest(["synthetic-protocol", slot, role])
            request = ctl.bound(
                dict(
                    episode_id=eid,
                    role=role,
                    slot_id=slot,
                    task_id=f"task-{i // 2}",
                    max_output_tokens=2048,
                )
            )
            requests[eid] = request
            jobs.append(
                dict(
                    episode_id=eid,
                    slot_id=slot,
                    task_id=request["task_id"],
                    role=role,
                    request_id=request["id"],
                    max_output_tokens=2048,
                    request_sha256=ctl.digest(request),
                    request_body_sha256=ctl.sha(ctl.canonical(request)),
                )
            )
        plan = dict(
            id="synthetic-plan",
            protocol_identity="synthetic-protocol",
            jobs=jobs,
            source_root="synthetic-only",
            source_protocol_id="old-source",
            source_batch_id="old-batch",
            concurrency={
                "max": 64,
                "ramp": [
                    {"settled_at_least": 0, "workers": 16},
                    {"settled_at_least": 16, "workers": 32},
                    {"settled_at_least": 64, "workers": 64},
                ],
            },
        )
        ctx = SimpleNamespace(
            output=tmp_path,
            jobs=jobs,
            pairs=list(zip(jobs[::2], jobs[1::2], strict=True)),
            plan=plan,
            progress={},
        )
        ctx.update = lambda **kw: ctx.progress.update(kw)
        ctx.request = lambda job: requests[job["episode_id"]]
        return ctx, MemoryLedger(capacity), provider

    return build


def execute(ctx, ledger):
    return asyncio.run(ctl.execute_reviews(ctx, ledger, api_key="synthetic-not-a-credential"))


def test_settlement_only_ramp_reaches_64_without_semantic_selection(setup):
    ctx, ledger, provider = setup(160)
    provider.overrides = {
        j["episode_id"]: dict(
            process_validity="unknown", process_candidate_usable=False, failure_codes=["RAW_JSON"]
        )
        for j in ctx.jobs
    }
    complete = execute(ctx, ledger)
    assert len(complete) == len(provider.calls) == len(set(provider.calls)) == 160
    assert provider.maximum == 64
    assert [ctl.ramp_limit(ctx.plan, n) for n in (0, 15, 16, 63, 64)] == [16, 16, 32, 32, 64]


def test_pending_reservations_reduce_concurrency_and_do_not_fake_budget_exhaustion(setup):
    ctx, ledger, provider = setup(20, capacity=2)
    complete = execute(ctx, ledger)
    assert len(complete) == len(provider.calls) == len(set(provider.calls)) == 20
    assert provider.maximum == 2 and ctx.progress["phase"] == "REVIEW_TERMINALS_COMPLETE"


def test_drained_wallet_that_cannot_admit_one_request_saves_without_sending(setup):
    ctx, ledger, provider = setup(capacity=0)
    assert execute(ctx, ledger) is None
    assert not provider.calls and not ledger.rows
    assert ctx.progress["phase"] == "BUDGET_SAVED"


def test_resume_only_unsent_reserved_and_reuse_settled_without_resend(setup):
    ctx, ledger, provider = setup()
    first = ctx.jobs[0]
    iid = ctl.iid_for(ledger, first)
    ledger.rows[iid] = dict(
        invocation_id=iid,
        state="RESERVED",
        dispatched_at=None,
        reserved_microcny=100,
        request_sha256=first["request_sha256"],
        response_body=None,
        http_status=None,
        usage_json=None,
        settled_microcny=None,
        evidence_json=None,
    )
    complete = execute(ctx, ledger)
    assert len(provider.calls) == 4 and provider.resume_flags[0] is True
    assert execute(ctx, ledger) == complete and len(provider.calls) == 4
    ledger.rows[iid].update(state="DISPATCHED", dispatched_at=1)
    with pytest.raises(ctl.SavedStop, match="must not be resent"):
        execute(ctx, ledger)
    assert len(provider.calls) == 4


def test_three_same_wave_network_unknowns_drain_ack_and_save_no_retry(setup):
    ctx, ledger, provider = setup(20)
    provider.failures = {j["episode_id"]: "network" for j in ctx.jobs[:3]}
    assert execute(ctx, ledger) is None
    assert ctx.progress["phase"] == "NETWORK_SAFETY_SAVED"
    assert len(provider.calls) == 16 and len(set(provider.calls)) == 16
    assert (
        ledger.snapshot()["pending_requests"]
        == ledger.snapshot()["unacknowledged_unknown_requests"]
        == 0
    )
    assert (
        sum(r["reserved_microcny"] for r in ledger.rows.values() if r["state"] == "UNKNOWN") == 300
    )
    assert ledger.halt is None
    complete = execute(ctx, ledger)
    assert len(complete) == len(provider.calls) == 20
    assert (
        sum(t["terminal_kind"] == "acknowledged_connection_unknown" for t in complete.values()) == 3
    )


def test_http_service_unknown_is_not_autoacknowledged_or_retried(setup):
    ctx, ledger, provider = setup()
    provider.failures[ctx.jobs[0]["episode_id"]] = "service"
    assert execute(ctx, ledger) is None
    assert ctx.progress["phase"] == "SERVICE_OR_LOCAL_SAVED"
    assert ledger.halt is not None and not ledger.acks
    assert len(provider.calls) == len(set(provider.calls))


def test_full_seal_keeps_projection_failed_and_reason_zero_candidates_and_stops_here(
    setup, monkeypatch
):
    ctx, ledger, provider = setup(6)
    provider.overrides[ctx.jobs[0]["episode_id"]] = dict(
        projection_usable=False, failure_codes=["PROJECTION"]
    )
    provider.overrides[ctx.jobs[2]["episode_id"]] = dict(
        process_candidate_usable=False, failure_codes=["OUTPUT_LIMIT"]
    )
    monkeypatch.setattr(ctl, "SIDE_COUNT", 6)
    monkeypatch.setattr(ctl, "PAIR_COUNT", 3)
    monkeypatch.setattr(
        ctl,
        "resolve_candidate_pair",
        lambda a, b, q_native: ctl.bound(
            dict(
                joint_process_candidate=True,
                candidate_gate=True,
                production_admitted=False,
                synthetic_not_a_real_V11_pair=True,
            )
        ),
    )
    complete = execute(ctx, ledger)
    with pytest.raises(ValueError, match="partial matrix"):
        ctl.freeze_review_seal(ctx, dict(list(complete.items())[:-1]))
    seal = ctl.freeze_review_seal(ctx, complete)
    assert seal["actual_returns"] == 6 and seal["network_unknowns"] == 0
    assert seal["joint_process_candidate_slot_ids"] == [
        ctx.jobs[0]["slot_id"],
        ctx.jobs[4]["slot_id"],
    ]
    assert seal["projection_blocked_candidate_slot_ids"] == [ctx.jobs[0]["slot_id"]]
    assert seal["candidate_positive_public_characters"] is None
    assert seal["no_joint_process_candidate_dropped"] and seal["no_reason0_package_dropped"]
    assert (
        not seal["mapping_started"]
        and not seal["training_started"]
        and not seal["production_admitted"]
    )
    assert not (ctx.output / "mapping").exists() and not (ctx.output / "training").exists()


def test_outer_projection_failure_never_exports_positive_offline_counts_as_usable(
    setup, monkeypatch
):
    ctx, ledger, provider = setup(2)
    provider.overrides[ctx.jobs[0]["episode_id"]] = dict(
        projection_usable=False, failure_codes=["SUPERVISION_REPRESENTATION_FAILED"]
    )
    original = provider.paid_record

    def paid_record(request, artifact, row):
        record = original(request, artifact, row)
        if request["role"] == "A":
            # Models quote=None passing an outer partial-quote failure while the
            # unchanged inner V11 interpretation regards the ID as a whole unit.
            record["inspection"]["reason_projection"].update(
                positive_public_characters=12, all_public_reasoning_masked=False
            )
        return ctl.bound({k: v for k, v in record.items() if k != "id"})

    monkeypatch.setattr(provider, "paid_record", paid_record)
    monkeypatch.setattr(ctl, "SIDE_COUNT", 2)
    monkeypatch.setattr(ctl, "PAIR_COUNT", 1)
    monkeypatch.setattr(
        ctl,
        "resolve_candidate_pair",
        lambda a, b, q_native: ctl.bound(
            dict(
                joint_process_candidate=True,
                candidate_gate=True,
                production_admitted=False,
                synthetic_not_a_real_V11_pair=True,
            )
        ),
    )
    seal = ctl.freeze_review_seal(ctx, execute(ctx, ledger))
    core = ctl.read_entry(seal["paired_cores"][0])
    assert core["offline_A_reason_projection"] == dict(
        raw_public_characters=12, positive_public_characters=12, all_public_reasoning_masked=False
    )
    assert core["A_reason_projection"] == dict(
        raw_public_characters=12, positive_public_characters=None, all_public_reasoning_masked=None
    )
    assert core["A_projection_usable"] is False and core["joint_process_candidate"] is True
    assert seal["joint_process_candidate_count"] == 1
    assert seal["candidate_raw_public_characters"] == 12
    assert seal["candidate_positive_public_characters"] is None
    assert seal["all_candidate_public_reasoning_masked"] is None
    assert not seal["projection_inventory_complete"]
