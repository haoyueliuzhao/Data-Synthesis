"""Capacity-revision controls on synthetic data/temp ledgers; zero real API/GPU."""

import asyncio
import copy
import json
import sqlite3
from types import SimpleNamespace

import pytest
from test_finance_research_probe_budget import sheet
from test_finance_research_probe_provider import Client
from test_finance_semantic_review import fixture_bundle
from test_finance_v6_compact_review import setup
from test_finance_v6_review_provider import response

from trusted_synthesis.finance_research import v6_review_revision as revision
from trusted_synthesis.finance_research.contracts import digest
from trusted_synthesis.finance_research.probe_budget import (
    V6_PURPOSE,
    V6_REVIEW_AMENDMENT_PAUSE,
    ProbeBudget,
    apply_v6_review_amendment,
)
from trusted_synthesis.finance_research.semantic_review import review_request
from trusted_synthesis.finance_research.v6_compact_review import capacity_features
from trusted_synthesis.finance_research.v6_review_provider import request_review


def write(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False))


@pytest.mark.parametrize("tokens,cap", [(0, 16384), (3000, 32768), (8000, 65536), (16000, 131072)])
def test_capacity_is_fixed_formula_smallest_discrete_cap_not_actual_token_claim(tokens, cap):
    value = revision.capacity_for(
        generation_output_tokens=tokens, target_span_count=0, action_count=0
    )
    assert value["estimated_requirement"] == (3 * (4096 + 3 * tokens) + 1) // 2
    assert value["max_output_tokens"] == cap
    assert not revision.CAPACITY_POLICY["actual_DeepSeek_review_token_prediction"]


@pytest.mark.parametrize("bad", [-1, True, 3.2])
def test_capacity_rejects_nonactual_counts_and_never_clips_over_131072(bad):
    with pytest.raises(ValueError, match="actual counts"):
        revision.capacity_for(generation_output_tokens=bad, target_span_count=0, action_count=0)
    with pytest.raises(ValueError, match="no truncation"):
        revision.capacity_for(generation_output_tokens=40000, target_span_count=0, action_count=0)


def test_build_inputs_uses_actual_fragment_feature_and_same_cap_for_both_reviewers(
    tmp_path, monkeypatch
):
    bundle = fixture_bundle()
    original = dict(
        id="prepared",
        bundle=bundle,
        requests=[review_request(bundle, {"answer": 120}, i) for i in (0, 1)],
    )
    monkeypatch.setattr(revision, "original_protocol", lambda: dict(task_ids=[bundle["task_id"]]))
    monkeypatch.setattr(revision, "checked_prepared", lambda *a: original)
    rows = revision.build_inputs(
        tmp_path, dict(generation_output_tokens_by_task={bundle["task_id"]: 3000})
    )
    payload = revision.read_json(
        revision.input_directory(tmp_path, bundle["task_id"]) / "record.json"
    )
    features = capacity_features(payload["requests"][0])
    assert payload["capacity"]["target_span_count"] == features["target_fragment_count"]
    assert payload["capacity"]["action_count"] == features["action_count"] == 8
    assert len(rows) == 1
    assert (
        payload["requests"][0]["max_output_tokens"] == payload["requests"][1]["max_output_tokens"]
    )
    assert payload["original_bundle_sha256"] == digest(bundle)


@pytest.mark.parametrize(
    "content,finish", [(None, "stop"), ("{broken", "stop"), ("{partial", "length")]
)
def test_null_format_and_length_failure_are_retained_not_repaired(content, finish):
    request, _ = setup()
    artifact = dict(content=content, finish_reason=finish)
    original = copy.deepcopy(artifact)
    assessment = revision.assess(artifact, request)
    assert not assessment["format_capacity_admitted"] and assessment["validated"] is None
    assert artifact == original


def test_format_gate_does_not_require_positive_semantic_result():
    request, answer = setup()
    for slot in answer["slots"]:
        slot["v_trace"] = "unknown"
    for relation in answer["relations"]:
        relation.update(relation="not_applicable", basis="not_applicable")
    assert revision.assess(dict(content=json.dumps(answer), finish_reason="stop"), request)[
        "format_capacity_admitted"
    ]


def _run_fixture(tmp_path, monkeypatch, *, bad_pilot=False, prior_main_failure=False):
    plan = dict(
        id="revision-control",
        task_ids=[f"task-{i}" for i in range(8)],
        calibration=dict(task_ids=[f"task-{i}" for i in range(6)]),
    )
    completed, dispatched, phases = {}, [], []
    ledger = SimpleNamespace(snapshot=lambda: {"halt": None}, unsettled=lambda: [])
    monkeypatch.setattr(revision, "checked_plan", lambda output: plan)
    monkeypatch.setattr(revision, "activate", lambda output, p: ledger)
    monkeypatch.setattr(revision, "recover", lambda output, p: completed)
    monkeypatch.setattr(revision, "_key", lambda path: "CPU no network")
    monkeypatch.setattr(revision, "status", lambda *args: None)

    def saved(task, reviewer, admitted):
        rid = revision.review_id(plan, task, reviewer)
        completed[rid] = dict(content="mock original", finish_reason="stop")
        write(
            revision.review_directory(tmp_path, rid) / "validation/record.json",
            dict(
                format_capacity_admitted=admitted,
                validated=None,
                error=None if admitted else {"reason": "length"},
            ),
        )

    if prior_main_failure:
        for task in plan["calibration"]["task_ids"]:
            for reviewer in (0, 1):
                saved(task, reviewer, True)
        saved("task-6", 0, False)

    async def batch(output, p, actual_ledger, key, actual_completed, jobs, phase):
        phases.append(phase)
        for task, reviewer in jobs:
            rid = revision.review_id(plan, task, reviewer)
            if rid in completed:
                continue
            dispatched.append((task, reviewer))
            if phase == "CAPACITY_CALIBRATION":
                saved(task, reviewer, not (bad_pilot and task == "task-0" and reviewer == 0))
        return []

    monkeypatch.setattr(revision, "run_batch", batch)
    return plan, completed, dispatched, phases


def test_fixed_twelve_failed_pilot_never_expands_or_retries_on_resume(tmp_path, monkeypatch):
    _, _, calls, phases = _run_fixture(tmp_path, monkeypatch, bad_pilot=True)
    asyncio.run(revision.run(tmp_path, tmp_path / "unused.env"))
    assert len(calls) == 12 and phases == ["CAPACITY_CALIBRATION"]
    original_gate = (tmp_path / "capacity_gate/record.json").read_bytes()
    asyncio.run(revision.run(tmp_path, tmp_path / "unused.env"))
    assert len(calls) == 12
    assert (tmp_path / "capacity_gate/record.json").read_bytes() == original_gate


def test_restart_after_nonpilot_format_failure_cannot_dispatch_remaining_reviews(
    tmp_path, monkeypatch
):
    _, _, calls, _ = _run_fixture(tmp_path, monkeypatch, prior_main_failure=True)
    asyncio.run(revision.run(tmp_path, tmp_path / "unused.env"))
    assert calls == []


def test_resume_cannot_flip_an_existing_failed_capacity_gate(tmp_path, monkeypatch):
    plan, _, calls, _ = _run_fixture(tmp_path, monkeypatch, bad_pilot=True)
    asyncio.run(revision.run(tmp_path, tmp_path / "unused.env"))
    rid = revision.review_id(plan, "task-0", 0)
    path = revision.review_directory(tmp_path, rid) / "validation/record.json"
    value = json.loads(path.read_bytes())
    value["format_capacity_admitted"] = True  # Deliberately corrupt only the temporary fixture.
    write(path, value)
    with pytest.raises(ValueError):
        asyncio.run(revision.run(tmp_path, tmp_path / "unused.env"))
    assert len(calls) == 12


def test_registration_refuses_uncommitted_source_before_auditing_paid_data(tmp_path, monkeypatch):
    touched = []
    monkeypatch.setattr(
        revision.subprocess,
        "check_output",
        lambda args, **kw: "frozen-head" if args[1] == "rev-parse" else b"not this source",
    )
    monkeypatch.setattr(revision, "historical_audit", lambda: touched.append(True))
    with pytest.raises(ValueError, match="commit capacity revision"):
        revision.register(tmp_path / "unregistered")
    assert touched == []


def test_checked_plan_binds_actual_runtime_and_supports_registration_subdirectory(
    tmp_path, monkeypatch
):
    plan = revision.bound(dict(runtime_binding={"module": "frozen"}))
    path = tmp_path / "registration/protocol.json"
    write(path, plan)
    monkeypatch.setattr(revision, "runtime_binding", lambda: {"module": "frozen"})
    assert revision.checked_plan(tmp_path) == plan
    monkeypatch.setattr(revision, "runtime_binding", lambda: {"module": "changed"})
    with pytest.raises(ValueError, match="source changed"):
        revision.checked_plan(tmp_path)


def _paid_fixture(tmp_path, monkeypatch):
    original = tmp_path / "original"
    original.mkdir()
    monkeypatch.setattr(revision, "ORIGINAL", original)
    path = original / "budget.sqlite3"
    old = ProbeBudget(
        path,
        run_id="original-run",
        price_sheet=sheet(),
        max_output_tokens=16384,
        purpose=V6_PURPOSE,
        request_cap=258000,
    )
    old_request = review_request(fixture_bundle(), {"answer": 120}, 0)
    historical_artifact = asyncio.run(
        request_review(
            ledger=old,
            api_key="temporary-mock-key",
            episode_id="old-review-preserved",
            request=old_request,
            client=Client(response()),
        )
    )
    old_row = old.request_record(historical_artifact["budget_invocation_id"])
    paid, _, _, _ = revision.paid_row(old_row, sheet())
    old.halt(reason=V6_REVIEW_AMENDMENT_PAUSE, invocation_id="user-audit")
    amendment_id = "new-capacity-review-plan"
    apply_v6_review_amendment(
        path,
        expected_run_id=old.run_id,
        expected_config_sha256=digest(old.config),
        amendment_id=amendment_id,
        allowed_review_output_limits=revision.ALLOWED_OUTPUTS,
        evidence={"user_authorized": True},
    )
    ledger = ProbeBudget(
        path,
        run_id=old.run_id,
        price_sheet=sheet(),
        max_output_tokens=131072,
        purpose=V6_PURPOSE,
        request_cap=258000,
        amendment_id=amendment_id,
        allowed_output_limits=revision.ALLOWED_OUTPUTS,
    )
    out = tmp_path / "revision"
    historical = revision.bound(dict(paid_entries=[paid]))
    write(out / "historical_audit/record.json", historical)
    plan = dict(
        id=amendment_id,
        historical_audit_id=historical["id"],
        task_ids=["task"],
        budget=dict(run_id=old.run_id, price_sheet=old.config["price_sheet"]),
    )
    request, answer = setup()
    request.update(max_output_tokens=32768, capacity_policy_id=revision.CAPACITY_POLICY["id"])
    payload = revision.bound(dict(requests=[request, setup(1)[0]]))
    input_path = revision.input_directory(out, "task") / "record.json"
    write(input_path, payload)
    plan["inputs"] = [
        dict(task_id="task", input_id=payload["id"], input_sha256=revision.sha(input_path))
    ]
    rid = revision.review_id(plan, "task", 0)
    artifact = asyncio.run(
        request_review(
            ledger=ledger,
            api_key="temporary-mock-key",
            episode_id=rid,
            request=request,
            client=Client(response(json.dumps(answer))),
        )
    )
    directory = revision.review_directory(out, rid)
    write(directory / "response/record.json", artifact)
    write(directory / "validation/record.json", revision.assess(artifact, request))
    return out, plan, ledger, request, artifact, directory


def test_recovery_preserves_old_spend_and_actual_per_request_cap(tmp_path, monkeypatch):
    output, plan, ledger, _, _, _ = _paid_fixture(tmp_path, monkeypatch)
    before = ledger.snapshot()
    completed = revision.recover(output, plan)
    assert len(completed) == 1 and before["requests_reserved"] == 2
    assert before["settled_tariff_microcny"] == 560 and ledger.snapshot() == before
    with sqlite3.connect(ledger.path) as db:
        limits = sorted(
            json.loads(r[0])["max_tokens"] for r in db.execute("SELECT request_body FROM requests")
        )
    assert limits == [16384, 32768]


def test_recovery_rejects_modified_validation_even_with_intact_paid_response(tmp_path, monkeypatch):
    output, plan, _, _, _, directory = _paid_fixture(tmp_path, monkeypatch)
    path = directory / "validation/record.json"
    altered = json.loads(path.read_bytes())
    altered["format_capacity_admitted"] = False
    write(path, altered)
    with pytest.raises(ValueError, match="validation|assessment"):
        revision.recover(output, plan)


def test_paid_original_body_cannot_be_relabelled_as_another_frozen_review_request(
    tmp_path, monkeypatch
):
    _, _, ledger, request, artifact, _ = _paid_fixture(tmp_path, monkeypatch)
    original = ledger.request_record(artifact["budget_invocation_id"])
    other = copy.deepcopy(request)
    other["messages"][1]["content"] += " changed scientific input"
    relabelled = copy.deepcopy(artifact)
    relabelled["semantic_review_request_sha256"] = digest(other)
    with pytest.raises(ValueError, match="request|body|wire"):
        revision.response_binding(relabelled, other, original)


def test_strict_successor_reuses_existing_paid_budget_without_new_authorization_or_reset(
    tmp_path, monkeypatch
):
    _, _, ledger, _, _, _ = _paid_fixture(tmp_path, monkeypatch)
    before = ledger.snapshot()
    config = ledger.config
    plan = dict(
        id="strict-successor-different-protocol",
        allowed_output_limits=revision.ALLOWED_OUTPUTS,
        original_budget_config_sha256=digest(config),
        budget=dict(
            path=str(ledger.path),
            run_id=ledger.run_id,
            purpose=V6_PURPOSE,
            hard_cap_microcny=config["hard_cap_microcny"],
            warning_microcny=config["warning_microcny"],
            request_cap=config["request_cap"],
            price_sheet=config["price_sheet"],
            amendment_id=config["amendment_id"],
            reuse_existing_amendment=True,
        ),
    )

    def no_new_amendment(*args, **kwargs):
        pytest.fail("strict schema successor must not reauthorize/reset the shared paid ledger")

    monkeypatch.setattr(revision, "apply_v6_review_amendment", no_new_amendment)
    output = tmp_path / "strict-successor"
    current = revision.activate(output, plan)
    assert current.snapshot() == before and current.config == config
    reuse = revision.read_json(output / "budget_amendment/record.json")
    assert reuse["reused"] and not reuse["new_monetary_authorization"]
    assert reuse["counters_at_reuse"]["settled_tariff_microcny"] == 560
    assert revision.activate(output, plan).snapshot() == before


@pytest.mark.parametrize(
    "admitted,count,wrong_ids",
    [(True, 12, False), (False, 11, False), (False, 13, False), (False, 12, True)],
)
def test_strict_parent_must_be_exact_failed_twelve_cohort_before_reusing_budget(
    tmp_path, monkeypatch, admitted, count, wrong_ids
):
    parent = revision.bound(
        dict(
            original_protocol_id="original",
            budget=dict(price_sheet=sheet().__dict__),
            calibration=dict(task_ids=[f"calibration-{i}" for i in range(6)]),
        )
    )
    directory = tmp_path / "parent"
    write(directory / "protocol.json", parent)
    write(
        directory / "capacity_gate/record.json",
        revision.bound(dict(protocol_id=parent["id"], admitted=admitted)),
    )
    ids = [
        revision.review_id(parent, task, index)
        for task in parent["calibration"]["task_ids"]
        for index in (0, 1)
    ]
    if wrong_ids:
        ids[-1] = revision.review_id(parent, "not-original-calibration", 0)
    completed = dict.fromkeys((ids + ["extra"])[:count], {})
    monkeypatch.setattr(revision, "recover", lambda *args: completed)
    write(directory / "historical_audit/record.json", {})

    def no_budget_open():
        pytest.fail("unadmitted parent cohort must fail before touching shared budget")

    monkeypatch.setattr(revision, "connect", no_budget_open)
    with pytest.raises(ValueError, match="cohort|calibration"):
        revision.historical_audit(directory)


def test_strict_review_arguments_and_format_flags_bind_actual_original_tool_call(
    tmp_path, monkeypatch
):
    from test_finance_v6_strict_review import setup as strict_setup
    from test_finance_v6_strict_review_provider import response_fixture

    _, _, ledger, _, _, _ = _paid_fixture(tmp_path, monkeypatch)
    request, semantic_review = strict_setup()
    request.update(max_output_tokens=32768, capacity_policy_id=revision.CAPACITY_POLICY["id"])
    raw_arguments = json.dumps(semantic_review)
    original = asyncio.run(
        request_review(
            ledger=ledger,
            api_key="temporary-mock-key",
            episode_id="strict-actual-response",
            request=request,
            client=Client(response_fixture(raw_arguments)),
        )
    )
    row = ledger.request_record(original["budget_invocation_id"])
    revision.response_binding(original, request, row)
    for key, replacement in (
        ("review_text", raw_arguments + "host repair"),
        ("review_format_error", "host rewrote format judgment"),
    ):
        changed = copy.deepcopy(original)
        changed[key] = replacement
        with pytest.raises(ValueError, match="strict|arguments|format|derived"):
            revision.response_binding(changed, request, row)
    malformed = response_fixture(raw_arguments)
    malformed["choices"][0]["message"]["tool_calls"][0]["id"] = ""
    failed = asyncio.run(
        request_review(
            ledger=ledger,
            api_key="temporary-mock-key",
            episode_id="strict-missing-id",
            request=request,
            client=Client(malformed),
        )
    )
    assert failed["review_text"] is None and failed["review_format_error"]
    # Correctly retained format failure is not confused with artifact tampering.
    revision.response_binding(
        failed, request, ledger.request_record(failed["budget_invocation_id"])
    )
    assert not revision.assess(failed, request)["format_capacity_admitted"]
