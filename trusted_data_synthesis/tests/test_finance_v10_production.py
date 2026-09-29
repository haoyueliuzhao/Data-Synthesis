"""Bounded controller controls on synthetic data/temp wallet; no real paid evidence."""

import asyncio
import copy
import json
import sqlite3
from types import SimpleNamespace

import httpx
import pytest
from test_finance_unknown_abandonment import table
from test_finance_v6_strict_review_provider import response_fixture
from test_finance_v10_budget import (  # noqa: F401
    BATCH_ID,
    SLOTS,
    register,
    stopped_history,
    synthetic_parent,
    wallet,
)
from test_finance_v10_process_review import fixture

from trusted_synthesis.finance_research import v10_production as prod
from trusted_synthesis.finance_research.contracts import digest
from trusted_synthesis.finance_research.storage import read_json
from trusted_synthesis.finance_research.v10_budget import generation_episode_id, review_episode_id
from trusted_synthesis.finance_research.v10_review_protocol import review_policy_definition
from trusted_synthesis.finance_research.v10_review_provider import request_body, request_review

KEY = "synthetic-review-memory-key-not-an-actual-credential"


class MockTransport:
    def __init__(self, responses, failures=None):
        self.responses, self.failures = responses, failures or {}
        self.calls = []

    async def __aenter__(self):
        return self

    async def __aexit__(self, *args):
        return False

    async def post(self, url, **kwargs):
        body = json.loads(kwargs["content"])
        key = digest(body)
        self.calls.append(key)
        await asyncio.sleep(0)  # Permit true in-flight overlap among local workers.
        if key in self.failures:
            raise self.failures[key]
        assert key in self.responses, "unexpected/undeclared simulated request"
        return SimpleNamespace(
            status_code=200,
            content=json.dumps(response_fixture(json.dumps(self.responses[key]))).encode(),
        )


@pytest.fixture
def cohort(wallet, tmp_path, monkeypatch):  # noqa: F811
    episode, candidate, raw = fixture()
    slots = [
        {
            **s,
            "task_id": episode.task_id,
            "slot_id": generation_episode_id(BATCH_ID, episode.task_id, s["slot_index"]),
        }
        if s["task_id"] == SLOTS[0]["task_id"]
        else dict(s)
        for s in SLOTS
    ]
    register(wallet, generation_slots=slots)
    policy = review_policy_definition()
    output = tmp_path / "production"
    plan = prod.bound(
        dict(
            batch_id=BATCH_ID,
            concurrency=8,
            slots=slots,
            task_ids=list(dict.fromkeys(s["task_id"] for s in slots)),
            policy=policy,
            review_policy_id=policy["id"],
            budget_database=str(wallet.path),
        )
    )
    generation = prod.bound(dict(protocol_id=plan["id"], slots=[{"slot": s} for s in slots]))
    native = prod.bound(
        dict(
            protocol_id=plan["id"],
            generation_seal_id=generation["id"],
            M=2,
            rows=[
                dict(slot=s, Q_native=index < 2, native=candidate["native_result"])
                for index, s in enumerate(slots)
            ],
        )
    )
    prod.publish(output / "generation_seal", generation)
    prod.publish(output / "native_support", native)
    for slot in slots[:2]:
        original = prod.slot_directory(output, slot)
        prod.publish(original / "episode", episode.model_dump(mode="json"), "episode.json")
        integrity = prod.bound(dict(episode_sha256=digest(episode), checks=candidate["integrity"]))
        prod.publish(original / "integrity", integrity)
        prod.publish(
            original / "outcome",
            prod.bound(
                dict(
                    status="COMPLETE",
                    protocol_id=plan["id"],
                    episode_path=str(original / "episode/episode.json"),
                    episode_sha256=digest(episode),
                    episode_file_sha256=prod.sha(original / "episode/episode.json"),
                    integrity_path=str(original / "integrity/record.json"),
                    integrity_id=integrity["id"],
                )
            ),
        )
    phase = prod.register_review_phase(output, plan)
    prod.register_runtime(output, plan, wallet)
    context = prod.Context(output, plan, phase)
    requests = {j["episode_id"]: context.request(j) for j in phase["jobs"]}
    responses = {}
    for request in requests.values():
        text = json.loads(
            json.dumps(raw).replace(candidate["slot_id"] + "/", request["slot_id"] + "/")
        )
        if request["role"] == "B":
            text = {"process": text["process"]}
        responses[digest(request_body(request))] = text
    transport = MockTransport(responses)
    monkeypatch.setattr(prod, "_key", lambda path: KEY)
    monkeypatch.setattr(prod, "direct_client", lambda **kw: transport)
    return SimpleNamespace(
        ledger=wallet,
        plan=plan,
        output=output,
        phase=phase,
        context=context,
        requests=requests,
        transport=transport,
        slots=slots,
    )


def run_reviews(cohort):
    return asyncio.run(
        prod.execute_stage(
            cohort.output, cohort.plan, cohort.ledger, cohort.context, cohort.phase["jobs"]
        )
    )


def test_registration_exact_2M_and_old_terminal_identity_not_reused(cohort):
    assert cohort.phase["M"] == 2 and len(cohort.phase["jobs"]) == 4
    assert {j["slot_id"] for j in cohort.phase["jobs"]} == {s["slot_id"] for s in cohort.slots[:2]}
    assert all(j["episode_id"].startswith("v10review:") for j in cohort.phase["jobs"])
    assert cohort.phase["primary_supervision_authority"] == "A" and not cohort.phase["third_review"]
    job = cohort.phase["jobs"][0]
    prod.publish(
        prod.job_directory(cohort.output, job) / "record",
        prod.bound(dict(episode_id="v8prod:old-original")),
    )
    with pytest.raises(ValueError, match="identity"):
        prod.gather_terminals(cohort.output, cohort.phase["jobs"])


def test_full_actual_returns_A_authority_AB_blind_and_once_full_mapping(cohort):
    original_requests = copy.deepcopy(cohort.requests)
    completed = run_reviews(cohort)
    assert len(completed) == len(cohort.transport.calls) == 4
    seal = prod.complete_review_seal(cohort.output, cohort.plan, cohort.phase, completed)
    assert seal["returned"] == 4 and seal["network_unknowns"] == 0 and seal["expected_reviews"] == 4
    assert len(seal["joint_slot_ids"]) == 2 and seal["N"] == 1
    for job in cohort.phase["jobs"]:
        request = cohort.context.request(job)
        assert request == original_requests[job["episode_id"]]
        text = json.dumps(request_body(request))
        assert "not-for-process-model" not in text and "execution_accuracy" not in text
        if job["role"] == "B":
            assert set(request["strict_tool"]["function"]["parameters"]["properties"]) == {
                "process"
            }
    for ref in seal["joint_records"].values():
        joint = prod.read_entry(ref)
        assert joint["supervision_authority"] == "A"
        assert joint["A_manifest"] == joint["A"]["supervision_manifest"]
        assert joint["B"]["supervision_manifest"] is None
    jobs = prod.mapping_jobs(cohort.plan, seal)
    assert len(jobs) == 1 and jobs[0]["slot_ids"] == seal["joint_slot_ids"]
    request = cohort.context.request(jobs[0])
    assert [p["slot_id"] for p in request["packages"]] == seal["joint_slot_ids"]
    assert len(cohort.transport.calls) == 4  # Request preparation is not another model call.


def test_successful_subset_never_substitutes_for_complete_2M(cohort):
    completed = run_reviews(cohort)
    partial = {
        key: val
        for key, val in completed.items()
        if val["request"]["slot_id"] == cohort.slots[0]["slot_id"]
    }
    assert len(partial) == 2 and all(r["process_validity"] == "valid" for r in partial.values())
    with pytest.raises(ValueError, match="all 2M"):
        prod.complete_review_seal(cohort.output, cohort.plan, cohort.phase, partial)
    wrong = {**cohort.phase, "jobs": cohort.phase["jobs"][:2]}
    with pytest.raises(ValueError, match="fixed complete 2M"):
        prod.complete_review_seal(cohort.output, cohort.plan, wrong, partial)
    assert not (cohort.output / "review_seal").exists()


def test_network_missing_return_counts_terminal_but_not_paid_verdict_or_material(cohort):
    job = cohort.phase["jobs"][-1]
    cohort.transport.failures[digest(request_body(cohort.requests[job["episode_id"]]))] = (
        httpx.ReadError("synthetic missing reply")
    )
    completed = run_reviews(cohort)
    assert len(completed) == len(cohort.transport.calls) == 4
    missing = completed[job["episode_id"]]
    assert missing["original_response"] is missing["usage"] is None
    assert not missing["actual_model_call_receipt_verified"] and not missing["material_eligible"]
    seal = prod.complete_review_seal(cohort.output, cohort.plan, cohort.phase, completed)
    assert seal["returned"] == 3 and seal["network_unknowns"] == 1
    assert len(seal["joint_records"]) == 2 and len(seal["joint_slot_ids"]) == 1
    assert len(cohort.transport.calls) == len(set(cohort.transport.calls))


def test_returned_annotation_failure_is_retained_without_percentage_stop_or_third_review(cohort):
    job = cohort.phase["jobs"][-1]
    malformed = {"unexpected_mask": ["original model output retained"]}
    cohort.transport.responses[digest(request_body(cohort.requests[job["episode_id"]]))] = malformed
    completed = run_reviews(cohort)
    record = completed[job["episode_id"]]
    assert record["actual_model_call_receipt_verified"]
    assert (
        record["review_status"] == "annotation_failed" and record["process_validity"] == "unknown"
    )
    assert record["artifact"]["review_text"] == json.dumps(malformed)
    seal = prod.complete_review_seal(cohort.output, cohort.plan, cohort.phase, completed)
    assert seal["returned"] == 4 and seal["network_unknowns"] == 0
    assert len(seal["joint_records"]) == 2 and len(seal["joint_slot_ids"]) == 1
    assert len(cohort.transport.calls) == 4 and not cohort.ledger.snapshot()["halt"]


def test_mapping_unknown_retains_joint_packages_and_cannot_be_empty_subset_ready(cohort):
    seal = prod.complete_review_seal(cohort.output, cohort.plan, cohort.phase, run_reviews(cohort))
    jobs = prod.mapping_jobs(cohort.plan, seal)
    request = cohort.context.request(jobs[0])
    cohort.transport.responses[digest(request_body(request))] = dict(
        mapping_status="unknown",
        states=[],
        ambiguities=[
            dict(
                slot_ids=seal["joint_slot_ids"],
                description="Unresolved behavioral alignment.",
                evidence=[],
            )
        ],
    )
    completed = asyncio.run(
        prod.execute_stage(cohort.output, cohort.plan, cohort.ledger, cohort.context, jobs)
    )
    before = copy.deepcopy(seal["joint_by_task"])
    with pytest.raises(ValueError, match="entire jointly valid"):
        prod.complete_mapping_seal(cohort.output, cohort.plan, seal, [], {})
    mapping = prod.complete_mapping_seal(cohort.output, cohort.plan, seal, jobs, completed)
    assert mapping["all_registered_jobs_terminal"] and not mapping["all_joint_states_resolved"]
    assert (
        mapping["mapping_status_counts"] == {"unknown": 1} and not mapping["hard_packages_deleted"]
    )
    assert seal["joint_by_task"] == before and len(next(iter(before.values()))) == 2


def test_settled_rows_restore_exact_artifacts_without_http_or_new_settlement(cohort):
    async def send_originals():
        for request in cohort.requests.values():
            await request_review(
                ledger=cohort.ledger, api_key=KEY, request=request, client=cohort.transport
            )

    asyncio.run(send_originals())
    before = {n: table(cohort.ledger.path, n) for n in ("requests", "counters", "events")}
    assert len(cohort.transport.calls) == 4
    completed = run_reviews(cohort)
    assert len(completed) == len(cohort.transport.calls) == 4
    assert all(table(cohort.ledger.path, n) == rows for n, rows in before.items())
    assert (
        prod.recover_stage(
            cohort.output, cohort.plan, cohort.ledger, cohort.context, cohort.phase["jobs"]
        )
        == completed
    )
    assert len(cohort.transport.calls) == 4


@pytest.mark.parametrize("failure", ["budget", "local"])
def test_budget_or_local_failure_saves_stops_and_never_loops_review(cohort, monkeypatch, failure):
    calls = []
    original = cohort.context.request
    if failure == "budget":
        with sqlite3.connect(cohort.ledger.path) as db:
            db.execute("UPDATE v10_quotas SET spent=549999999 WHERE category='review_mapping'")
            db.execute("UPDATE counters SET spent=spent+549999999")

    def request(job):
        calls.append(job["episode_id"])
        if failure == "local":
            raise ValueError("synthetic source binding failure")
        return original(job)

    monkeypatch.setattr(cohort.context, "request", request)
    assert run_reviews(cohort) is None
    assert len(calls) == len(set(calls)) == 1 and not cohort.transport.calls
    assert cohort.ledger.snapshot()["pending_requests"] == 0
    assert not (cohort.output / "review_seal").exists()


def test_local_error_does_not_gain_retry_from_another_inflight_network_unknown(cohort, monkeypatch):
    network, local = cohort.phase["jobs"][:2]
    cohort.transport.failures[digest(request_body(cohort.requests[network["episode_id"]]))] = (
        httpx.ReadError("synthetic overlapping network error")
    )
    calls = []
    original = cohort.context.request

    def request(job):
        calls.append(job["episode_id"])
        if job["episode_id"] == local["episode_id"]:
            raise ValueError("synthetic local binding failure")
        return original(job)

    monkeypatch.setattr(cohort.context, "request", request)
    assert run_reviews(cohort) is None
    assert calls.count(local["episode_id"]) == 1
    assert len(cohort.transport.calls) == 1
    assert cohort.ledger.snapshot()["pending_requests"] == 0
    assert cohort.ledger.snapshot()["unacknowledged_unknown_requests"] == 1
    assert not (cohort.output / "review_seal").exists()
    errors = list(cohort.output.glob("reviews/*/*/controller_errors/*/record.json"))
    assert any(read_json(p)["network_only_continuation_candidate"] is False for p in errors)


def test_runtime_16_is_prospective_same_policy_and_exact_resume(cohort):
    path = cohort.output / prod.RUNTIME_PATH
    original = path.read_bytes()
    policy_before = copy.deepcopy(cohort.plan["policy"])
    counters_before = table(cohort.ledger.path, "counters")
    runtime = prod.register_runtime(cohort.output, cohort.plan, cohort.ledger)
    assert runtime["effective_concurrency"] == {"generation": 8, "review": 16, "mapping": 16}
    assert runtime["policy_id"] == cohort.plan["review_policy_id"]
    assert runtime["authorization"]["user_reply"] == "批准后续审阅／映射并发 16"
    assert runtime["authorization"]["date"] == "2026-09-29"
    assert runtime["annotation_requests_before_registration"] == 0
    assert runtime["samples_semantics_masks_model_budget_and_zero_retries_unchanged"]
    assert cohort.plan["policy"] == policy_before and policy_before["concurrency"] == 8
    assert table(cohort.ledger.path, "counters") == counters_before
    assert len(run_reviews(cohort)) == 4
    assert prod.register_runtime(cohort.output, cohort.plan, cohort.ledger) == runtime
    assert path.read_bytes() == original
    status = read_json(cohort.output / "status.json")
    assert status["runtime_revision_id"] == runtime["id"]
    assert status["registered_stage_concurrency"] == 16


def test_runtime_refuses_retroactive_or_changed_configuration_and_other_batch(cohort):
    runtime = prod.register_runtime(cohort.output, cohort.plan, cohort.ledger)
    assert len(run_reviews(cohort)) == 4
    missing = cohort.output / "missing-prior-runtime"
    with pytest.raises(ValueError, match="before the first annotation"):
        prod.register_runtime(missing, cohort.plan, cohort.ledger)
    assert not missing.exists()
    conflicting = cohort.output / "conflicting-runtime"
    wrong = {k: v for k, v in runtime.items() if k != "id"}
    wrong["effective_concurrency"] = {"generation": 8, "review": 8, "mapping": 8}
    prod.publish((conflicting / prod.RUNTIME_PATH).parent, prod.bound(wrong))
    original = (conflicting / prod.RUNTIME_PATH).read_bytes()
    with pytest.raises(ValueError, match="runtime differs"):
        prod.register_runtime(conflicting, cohort.plan, cohort.ledger)
    assert (conflicting / prod.RUNTIME_PATH).read_bytes() == original
    with pytest.raises(ValueError, match="only this original batch"):
        prod.register_runtime(
            cohort.output, {**cohort.plan, "batch_id": "future-not-authorized"}, cohort.ledger
        )


def test_runtime_controls_sixteen_simultaneous_workers_not_just_status_label(cohort, monkeypatch):
    jobs = [
        dict(
            kind="review",
            task_id=slot["task_id"],
            slot_id=slot["slot_id"],
            role=role,
            episode_id=review_episode_id(BATCH_ID, slot["slot_id"], role),
        )
        for slot in cohort.slots[:9]
        for role in ("A", "B")
    ][:17]
    context = SimpleNamespace(
        request=lambda job: dict(
            id=digest(job), episode_id=job["episode_id"], max_output_tokens=2048
        )
    )
    active, maximum, calls = 0, 0, []

    async def synthetic_request(**kwargs):
        nonlocal active, maximum
        active += 1
        maximum = max(maximum, active)
        calls.append(kwargs["request"]["episode_id"])
        await asyncio.sleep(0.005)
        active -= 1
        return dict(synthetic_scheduling_only=True)

    monkeypatch.setattr(prod, "request_review", synthetic_request)
    monkeypatch.setattr(
        prod,
        "review_record",
        lambda request, artifact, row: prod.bound(
            dict(
                schema="synthetic_scheduling_only",
                request=request,
                actual_model_call_receipt_verified=False,
                synthetic_not_paid_evidence=True,
            )
        ),
    )
    before = table(cohort.ledger.path, "counters")
    completed = asyncio.run(
        prod.execute_stage(cohort.output, cohort.plan, cohort.ledger, context, jobs)
    )
    assert len(completed) == len(calls) == 17 and maximum == 16 and active == 0
    assert table(cohort.ledger.path, "counters") == before
    assert all(r["synthetic_not_paid_evidence"] for r in completed.values())
