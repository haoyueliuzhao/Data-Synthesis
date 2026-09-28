"""Small decomposed-controller controls; no 18000-run simulation or real API/DB/GPU."""

import asyncio
import copy
import json
import sqlite3
from types import SimpleNamespace

import pytest
from test_finance_research_probe_budget import sheet
from test_finance_research_probe_provider import Client
from test_finance_v6_review_revision import _paid_fixture, write
from test_finance_v6_slot_review import setup as slot_setup
from test_finance_v6_strict_review_provider import response_fixture

from trusted_synthesis.finance_research import v6_decomposed_review as controller
from trusted_synthesis.finance_research.contracts import digest
from trusted_synthesis.finance_research.v6_review_provider import request_review


def job(stage, task, reviewer=0, slot=None, workload=10):
    return dict(
        stage=stage,
        task_id=task,
        reviewer=reviewer,
        slot_id=slot,
        key=controller.job_key(stage, task, reviewer, slot),
        capacity=dict(workload=workload),
    )


def completed(accepted=True, *, cost=100, truncated=False, semantic=False):
    return dict(
        artifact=dict(peak_tariff_upper_bound_microcny=cost),
        assessment=dict(
            interface_admitted=accepted,
            semantic_consistent=semantic,
            output_truncated=truncated,
            v_trace="unknown",
        ),
    )


def test_stage_slot_reviewer_and_protocol_are_distinct_invocation_namespaces():
    jobs = [job("slot", "task", i, f"s{s}") for s in range(8) for i in (0, 1)]
    jobs += [job("alignment", "task", i) for i in (0, 1)]
    assert len({j["key"] for j in jobs}) == 18
    names = {controller.episode_id({"id": "R3"}, j) for j in jobs}
    assert len(names) == 18
    assert names.isdisjoint(controller.episode_id({"id": "old-R2"}, j) for j in jobs)


def test_95_percent_gate_is_mechanical_not_positive_and_truncation_is_separate():
    jobs = [job("slot", str(i)) for i in range(96)]
    done = {j["key"]: completed(i < 92) for i, j in enumerate(jobs)}
    gate = controller.interface_gate(jobs, done)
    assert gate["admitted"] and gate["required_passes"] == 92
    assert gate["semantic_consistency_count"] == 0 and not gate["positive_verdict_required"]
    done[jobs[0]["key"]]["assessment"]["interface_admitted"] = False
    assert not controller.interface_gate(jobs, done)["admitted"]
    done[jobs[0]["key"]]["assessment"]["interface_admitted"] = True
    done[jobs[0]["key"]]["assessment"]["output_truncated"] = True
    assert not controller.interface_gate(jobs, done)["admitted"]
    alignment = [job("alignment", str(i)) for i in range(12)]
    assert controller.interface_gate(alignment, {})["required_passes"] == 12


@pytest.mark.parametrize("finish,error", [("length", None), ("tool_calls", "missing tool id")])
def test_interface_failure_placeholder_preserves_coordinates_and_cannot_be_positive(finish, error):
    request, _ = slot_setup()
    selected = job("slot", request["task_id"], slot=request["slot_id"])
    artifact = dict(finish_reason=finish, review_text=None, review_format_error=error)
    value = controller.assess(selected, artifact, request)
    assert not value["interface_admitted"] and value["v_trace"] == "unknown"
    assert value["parsed"] is value["derived"] is value["validation"] is None
    assert value["reviewer"] == selected["reviewer"] and value["slot_id"] == selected["slot_id"]
    assert value["task_bundle_sha256"] == request["task_bundle_sha256"]
    assert value["output_truncated"] == (finish == "length")


def test_semantic_inconsistency_is_unknown_material_not_a_failed_technical_gate():
    request, raw = slot_setup()
    raw["propositions"][0]["judgment"] = "contradicted"
    value = controller.assess(
        job("slot", request["task_id"], slot="s0"),
        dict(finish_reason="tool_calls", review_format_error=None, review_text=json.dumps(raw)),
        request,
    )
    assert value["interface_admitted"] and not value["semantic_consistent"]
    assert value["validation"]["v_trace"] == "unknown"
    assert value["validation"]["positive_target_mask"] is None


def test_alignment_waits_for_both_complete_slot_chains_and_preserves_failed_interface_placeholders(
    tmp_path, monkeypatch
):
    from test_finance_semantic_review import fixture_bundle, mechanical

    from trusted_synthesis.finance_research.v6_slot_review import slot_review_request

    bundle = fixture_bundle()
    prepared = dict(bundle=bundle, mechanical=mechanical())
    task_id = bundle["task_id"]
    jobs = [
        job("slot", task_id, reviewer, slot["slot_id"])
        for slot in bundle["slots"]
        for reviewer in (0, 1)
    ]
    alignment = [job("alignment", task_id, reviewer) for reviewer in (0, 1)]
    capacity = controller.bind_capacity(
        None, generation_tokens=0, fragments=0, actions=0, alignment=True
    )
    for selected in alignment:
        selected["capacity"] = capacity
    context = controller.Context(
        tmp_path, dict(id="R3-unknown-placeholders", task_ids=[task_id], jobs=jobs + alignment)
    )
    monkeypatch.setattr(controller, "checked_prepared", lambda *args: prepared)
    for selected in jobs:
        request = slot_review_request(
            bundle, selected["slot_id"], {"answer": 120}, selected["reviewer"]
        )
        assessment = controller.assess(
            selected,
            dict(
                finish_reason="length",
                review_text=None,
                review_format_error="truncated actual output",
            ),
            request,
        )
        if selected is jobs[-1]:
            with pytest.raises(ValueError, match="barrier"):
                context.prepare_alignment(task_id)
        write(controller.job_directory(tmp_path, selected) / "assessment/record.json", assessment)
    context.prepare_alignment(task_id)
    for selected in alignment:
        request = context.request(selected)
        assert len(request["own_slot_reviews"]) == 8 and request["own_eligible_slot_ids"] == []
        assert all(
            value["v_trace"] == "unknown" and value["reviewer"] == selected["reviewer"]
            for value in request["own_slot_reviews"].values()
        )
        assert request["other_reviewer_output_visible"] is False


def test_budget_forecast_counts_only_remaining_jobs_and_never_claims_guarantee():
    jobs = [job("slot", str(i), workload=10) for i in range(3)]
    jobs += [job("alignment", str(i), workload=20) for i in range(2)]
    done = {jobs[0]["key"]: completed(cost=1000), jobs[3]["key"]: completed(cost=2000)}
    context = SimpleNamespace(plan=dict(jobs=jobs))
    value = controller.budget_forecast(
        context, done, SimpleNamespace(snapshot=lambda: {"remaining_exposure_microcny": 4000})
    )
    assert value["central_remaining_microcny"] == 4000 and value["admitted"]
    assert not value["statistical_confidence_interval"] and not value["guarantee_of_completion"]
    assert not controller.budget_forecast(
        context, done, SimpleNamespace(snapshot=lambda: {"remaining_exposure_microcny": 3999})
    )["admitted"]


def paid_context(tmp_path, monkeypatch):
    _, _, ledger, _, _, _ = _paid_fixture(tmp_path, monkeypatch)
    with sqlite3.connect(ledger.path) as db:
        db.row_factory = sqlite3.Row
        prefix = [
            controller.paid_row(row, sheet())[0] for row in db.execute("SELECT * FROM requests")
        ]
    output = tmp_path / "R3"
    history = controller.bound(dict(paid_entries=prefix))
    write(output / "historical_audit/record.json", history)
    request, answer = slot_setup()
    request.update(max_output_tokens=16384, capacity_policy_id="R3-frozen-capacity")
    selected = job("slot", request["task_id"], slot=request["slot_id"])
    selected["request_sha256"] = digest(request)
    payload = controller.bound(dict(requests={selected["key"]: request}))
    path = controller.task_inputs(output, selected["task_id"]) / "record.json"
    write(path, payload)
    plan = dict(
        id="R3-local-control",
        historical_audit_id=history["id"],
        jobs=[selected],
        task_ids=[selected["task_id"]],
        budget=dict(run_id=ledger.run_id, price_sheet=ledger.config["price_sheet"]),
        slot_inputs={selected["task_id"]: dict(id=payload["id"], sha256=controller.sha(path))},
    )
    context = controller.Context(output, plan)
    artifact = asyncio.run(
        request_review(
            ledger=ledger,
            api_key="R3-CPU-mock-secret",
            episode_id=controller.episode_id(plan, selected),
            request=request,
            client=Client(response_fixture(json.dumps(answer))),
        )
    )
    directory = controller.job_directory(output, selected)
    write(directory / "started/record.json", dict(job_key=selected["key"]))
    write(directory / "response/record.json", artifact)
    assessment = controller.assess(selected, artifact, request)
    write(directory / "assessment/record.json", assessment)
    return context, ledger, selected, artifact, assessment, prefix


def test_recovery_conserves_entire_historical_prefix_and_stage_payment(tmp_path, monkeypatch):
    context, ledger, selected, _, _, prefix = paid_context(tmp_path, monkeypatch)
    before = ledger.snapshot()
    done = controller.recover(context)
    assert set(done) == {selected["key"]} and len(prefix) == 2
    assert before["settled_tariff_microcny"] == 840 and before["requests_reserved"] == 3
    assert ledger.snapshot() == before


@pytest.mark.parametrize("field", ["assessment", "response", "request"])
def test_derived_or_frozen_source_changes_are_rejected_without_new_payment(
    tmp_path, monkeypatch, field
):
    context, ledger, selected, artifact, assessment, _ = paid_context(tmp_path, monkeypatch)
    directory = controller.job_directory(context.output, selected)
    before = ledger.snapshot()
    if field == "assessment":
        changed = copy.deepcopy(assessment)
        changed["interface_admitted"] = False
        write(directory / "assessment/record.json", changed)
    elif field == "response":
        changed = copy.deepcopy(artifact)
        changed["review_text"] += " fabricated supplement"
        write(directory / "response/record.json", changed)
    else:
        path = controller.task_inputs(context.output, selected["task_id"]) / "record.json"
        changed = json.loads(path.read_bytes())
        changed["requests"][selected["key"]]["messages"][1]["content"] += " changed source"
        write(path, changed)
    with pytest.raises(ValueError):
        controller.recover(context)
    assert ledger.snapshot() == before


def test_lost_old_paid_call_cannot_be_hidden_by_decrementing_counters(tmp_path, monkeypatch):
    context, ledger, _, _, _, prefix = paid_context(tmp_path, monkeypatch)
    with sqlite3.connect(ledger.path) as db:
        db.execute("DELETE FROM requests WHERE invocation_id=?", (prefix[0]["invocation_id"],))
        db.execute(
            "UPDATE counters SET requests=requests-1,dispatched=dispatched-1,spent=spent-?",
            (prefix[0]["settled_microcny"],),
        )
    with pytest.raises(ValueError, match="old paid calls|charges disappeared"):
        controller.recover(context)


def test_paid_response_missing_assessment_cannot_be_resent(tmp_path, monkeypatch):
    context, ledger, selected, _, _, _ = paid_context(tmp_path, monkeypatch)
    path = controller.job_directory(context.output, selected) / "assessment/record.json"
    path.rename(path.parent / "retained-backup.json")
    before = ledger.snapshot()
    with pytest.raises(ValueError, match="cannot be resent"):
        controller.recover(context)
    assert ledger.snapshot() == before


def test_early_failure_guard_persists_stop_even_if_later_window_would_pass(tmp_path, monkeypatch):
    jobs = [job("slot", str(i)) for i in range(9)]
    context = SimpleNamespace(
        output=tmp_path,
        plan=dict(
            id="R3-window-control",
            automatic_full_inventory_expansion=False,
            technical_gate=dict(task_ids=[j["task_id"] for j in jobs]),
        ),
        jobs={j["key"]: j for j in jobs},
    )
    done = {j["key"]: completed(i >= 3) for i, j in enumerate(jobs[:8])}  # five of eight
    ledger = SimpleNamespace(snapshot=lambda: {})
    failures = asyncio.run(
        controller.run_batch(context, ledger, "unused", done, jobs, "SLOT_REVIEWING", 1)
    )
    assert failures
    saved = (tmp_path / "dispatch_stop/record.json").read_bytes()
    for value in done.values():
        value["assessment"]["interface_admitted"] = True
    failures = asyncio.run(
        controller.run_batch(context, ledger, "unused", done, jobs, "SLOT_REVIEWING", 1)
    )
    assert failures and len(done) == 8
    assert (tmp_path / "dispatch_stop/record.json").read_bytes() == saved


def run_fixture(tmp_path, monkeypatch):
    jobs = [
        job("slot", "pilot", slot="p"),
        job("alignment", "pilot"),
        job("slot", "remaining", slot="r"),
        job("alignment", "remaining"),
    ]
    plan = dict(
        id="R3-forecast-control",
        jobs=jobs,
        task_ids=["pilot", "remaining"],
        technical_gate=dict(task_ids=["pilot"]),
        automatic_full_inventory_expansion=False,
        native_zero_support_task_ids=["remaining"],
    )
    context = SimpleNamespace(
        output=tmp_path,
        plan=plan,
        jobs={j["key"]: j for j in jobs},
        prepare_alignment=lambda task: None,
    )
    done = {jobs[0]["key"]: completed(cost=100), jobs[1]["key"]: completed(cost=100)}
    state = {"remaining_exposure_microcny": 10000}
    ledger = SimpleNamespace(snapshot=lambda: dict(state))
    monkeypatch.setattr(controller, "checked_plan", lambda output: plan)
    monkeypatch.setattr(controller, "Context", lambda *args: context)
    monkeypatch.setattr(controller, "ledger_for", lambda p: ledger)
    monkeypatch.setattr(controller, "recover", lambda ctx: done)
    monkeypatch.setattr(controller, "_key", lambda path: "CPU mock, never sent")
    monkeypatch.setattr(controller, "status", lambda *args: None)

    async def no_dispatch(ctx, budget, key, completed_map, selected, phase, concurrency):
        assert phase in {"PILOT_SLOT_REVIEW", "PILOT_ALIGNMENT"}, "no automatic full expansion"
        return []

    monkeypatch.setattr(controller, "run_batch", no_dispatch)
    return context, done, state


def test_successful_technical_cohort_and_forecast_still_wait_for_scope_choice(
    tmp_path, monkeypatch
):
    run_fixture(tmp_path, monkeypatch)
    statuses = []
    monkeypatch.setattr(controller, "status", lambda output, value: statuses.append(value))
    asyncio.run(controller.run(tmp_path, tmp_path / "unused.env"))
    assert statuses[-1]["phase"] == "TECHNICAL_COHORT_COMPLETE_AWAITING_SCOPE"
    assert statuses[-1]["slot_gate"]["admitted"] and statuses[-1]["alignment_gate"]["admitted"]
    assert statuses[-1]["forecast"]["admitted"]
    assert (
        not statuses[-1]["training_started"] and not statuses[-1]["original_1000_training_possible"]
    )


def test_resume_reuses_frozen_pilot_forecast_without_reestimating_from_new_budget(
    tmp_path, monkeypatch
):
    _, _, state = run_fixture(tmp_path, monkeypatch)
    asyncio.run(controller.run(tmp_path, tmp_path / "unused.env"))
    forecast_path = tmp_path / "budget_forecast/record.json"
    original = forecast_path.read_bytes()
    state["remaining_exposure_microcny"] = 1
    monkeypatch.setattr(
        controller, "budget_forecast", lambda *a: pytest.fail("no new forecast on resume")
    )
    asyncio.run(controller.run(tmp_path, tmp_path / "unused.env"))
    assert forecast_path.read_bytes() == original


def test_forecast_or_gate_derived_record_cannot_be_modified_to_bypass_admission(
    tmp_path, monkeypatch
):
    run_fixture(tmp_path, monkeypatch)
    asyncio.run(controller.run(tmp_path, tmp_path / "unused.env"))
    path = tmp_path / "budget_forecast/record.json"
    changed = json.loads(path.read_bytes())
    changed["central_remaining_microcny"] = 0
    write(path, changed)
    with pytest.raises(ValueError, match="forecast"):
        asyncio.run(controller.run(tmp_path, tmp_path / "unused.env"))
