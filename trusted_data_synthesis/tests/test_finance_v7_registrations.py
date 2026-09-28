"""Focused V7 registration/R4 boundary controls: in-memory evidence, no DB/API/GPU."""

import asyncio
import copy
import hashlib
import json
import sqlite3
from collections import Counter
from dataclasses import asdict
from pathlib import Path
from types import SimpleNamespace

import pytest
from test_finance_research_probe_budget import sheet, usage
from test_finance_semantic_review import fixture_bundle

from trusted_synthesis.finance_research import v6_decomposed_review as shared
from trusted_synthesis.finance_research import v7_full_probe as full
from trusted_synthesis.finance_research import v7_review_locator_trial as trial
from trusted_synthesis.finance_research.contracts import (
    PublicSource,
    PublicTask,
    digest,
    invocation_identity,
)


@pytest.fixture(autouse=True)
def no_database_or_paid_calls(monkeypatch):
    def forbidden(*args, **kwargs):
        pytest.fail("this control must never access a database, credential or paid API")

    monkeypatch.setattr(sqlite3, "connect", forbidden)
    monkeypatch.setattr(shared, "request_review", forbidden)
    monkeypatch.setattr(shared, "_key", forbidden)


def config():
    return dict(
        run_id="original-shared-run",
        purpose="v6_joint_probe_and_review_v1",
        price_sheet=asdict(sheet()),
        hard_cap_microcny=800_000_000,
        warning_microcny=700_000_000,
        request_cap=258000,
        amendment_id="existing-cap-amendment",
        allowed_output_limits=[2048, 16384, 32768, 65536, 131072],
    )


def public_task(index, *, content="source", table=None):
    source = PublicSource(source_id="public", kind="text", locator="pre_text[0]", content=content)
    if table is not None:
        source = PublicSource(source_id="public", kind="table", locator="table", content=table)
    return PublicTask(
        dataset="finqa",
        task_id=f"task-{index}",
        question="Q",
        sources=(source,),
        version="synthetic",
    )


def old_plan():
    tasks = [f"task-{i}" for i in range(1000)]
    return dict(
        id="old-original-protocol",
        snapshot="synthetic-public-snapshot",
        snapshot_id="public-snapshot",
        task_ids=tasks,
        role_plan={"assignments": {"finqa/" + t: "sft" for t in tasks}},
        inventory={
            "slots": [
                dict(task_id=t, slot_index=s, slot_id=f"old:{t}:{s}")
                for t in tasks
                for s in range(8)
            ]
        },
    )


@pytest.mark.parametrize(
    "chars,cells,expected", [(8000, 0, 2048), (8001, 0, 16384), (1, 200, 2048), (1, 201, 16384)]
)
def test_capacity_depends_only_on_original_public_size(chars, cells, expected):
    task = public_task(0, content="x" * (chars - 1), table=[[""] * cells] if cells else None)
    value = full.public_capacity(task)
    assert value["max_new_tokens"] == expected and not value["uses_reference_or_old_success"]
    assert not value["actual_output_token_prediction"]


def test_full_batch_keeps_original1000_eight_new_slots_and_inherits_only_remaining_budget(
    monkeypatch,
):
    original = old_plan()
    tasks = [public_task(i) for i in range(1000)]
    tasks[0] = public_task(0, content="x" * 8000)
    monkeypatch.setattr(full, "original_protocol", lambda: original)
    monkeypatch.setattr(
        full, "load_public_snapshot", lambda path: ({"id": "public-snapshot"}, tasks, {})
    )
    monkeypatch.setattr(full, "verify_role_plan", lambda roles, public, lineage: None)
    monkeypatch.setattr(full, "runtime_binding", lambda: {"source": "test"})
    history = dict(
        id="retained-history",
        ledger_config=config(),
        counters={"spent": 123_000_001, "requests": 12345},
        review_gate_sha256="gate-file",
        review_gate={"admitted": False},
    )
    plan = full.build_plan("new-source-commit", history)
    assert plan["task_ids"] == original["task_ids"] and plan["task_denominator"] == 1000
    assert plan["slot_denominator"] == len(plan["slots"]) == 8000
    assert Counter(row["task_id"] for row in plan["slots"]) == {t: 8 for t in original["task_ids"]}
    assert len({row["slot_id"] for row in plan["slots"]}) == 8000
    assert not {row["slot_id"] for row in plan["slots"]} & {
        row["slot_id"] for row in original["inventory"]["slots"]
    }
    assert plan["capacity_histogram"] == {16384: 1, 2048: 999}
    budget = plan["budget"]
    assert budget["hard_cap_microcny"] == 800_000_000 and budget["request_cap"] == 258000
    assert budget["remaining_cost_microcny"] == 676_999_999
    assert (
        budget["remaining_request_budget"] == 245655 and budget["cost_and_request_caps_never_reset"]
    )
    assert not plan["execution_admitted"] and plan["new_model_calls"] == 0
    assert plan["registration_status"] == "REGISTERED_NOT_STARTED" and not plan["training_started"]
    assert not plan["sampling"]["unsupported_parallel_tool_calls_parameter_sent"]


class MemoryConnection:
    def __init__(self, rows, cfg):
        self.rows, self.cfg, self.halt = rows, cfg, None
        self.counters = dict(
            spent=sum(row["settled_microcny"] for row in rows),
            requests=len(rows),
            held=0,
            pending=0,
            unknown=0,
        )

    def __enter__(self):
        return self

    def __exit__(self, *args):
        return False

    def execute(self, sql):
        if "key='halt'" in sql:
            return SimpleNamespace(fetchone=lambda: self.halt)
        if "key='config'" in sql:
            return SimpleNamespace(fetchone=lambda: (json.dumps(self.cfg),))
        if "FROM requests" in sql:
            return iter(self.rows)
        assert "FROM counters" in sql
        return SimpleNamespace(fetchone=lambda: self.counters)


def history_fixture(monkeypatch, module, *, completed=15):
    cfg = config()
    parent = shared.bound(
        dict(
            budget=copy.deepcopy(cfg),
            allowed_output_limits=cfg["allowed_output_limits"],
            technical_gate={"task_ids": [f"task-{i}" for i in range(6)]},
        )
    )
    gate = shared.bound(dict(protocol_id=parent["id"], admitted=False, actual_calls=completed))
    rows = []
    counts = usage()
    for index in range(completed):
        coordinates = invocation_identity(
            dict(run_id=cfg["run_id"], episode_id=f"failed-R3-{index}", attempt_index=1),
            turn_index=0,
        )
        request = json.dumps(
            dict(model="deepseek-flash", thinking={"type": "disabled"}, max_tokens=16384)
        ).encode()
        response = json.dumps(dict(model="deepseek-flash", usage=counts)).encode()
        rows.append(
            dict(
                state="SETTLED",
                dispatched_at="synthetic-time",
                request_body=request,
                response_body=response,
                request_sha256=hashlib.sha256(request).hexdigest(),
                response_sha256=hashlib.sha256(response).hexdigest(),
                usage_json=json.dumps(counts),
                coordinates_json=json.dumps(coordinates),
                invocation_id=coordinates["invocation_id"],
                settled_microcny=sheet().cost_microcny(hit=41, miss=59, output=20),
            )
        )
    connection = MemoryConnection(rows, cfg)
    monkeypatch.setattr(module, "connect", lambda: connection)
    if hasattr(module, "Context"):
        monkeypatch.setattr(module, "Context", lambda *args: "synthetic-recovery-context")
        monkeypatch.setattr(
            module, "recover", lambda context: {str(i): {"failed": True} for i in range(completed)}
        )
    monkeypatch.setattr(
        module, "read_json", lambda path: parent if str(path).endswith("protocol.json") else gate
    )
    monkeypatch.setattr(module, "sha", lambda path: digest(str(path)))
    return parent, connection


def test_R4_accepts_failed_partial15_without_removing_a_paid_failure(monkeypatch):
    parent, connection = history_fixture(monkeypatch, trial)
    actual_parent, result = trial.history()
    assert actual_parent == parent and result["parent_actual_calls"] == 15
    assert len(result["paid_entries"]) == 15 and result["no_prior_failures_or_costs_removed"]
    assert result["budget_counters"]["spent"] == sum(
        row["settled_microcny"] for row in connection.rows
    )
    connection.rows[-1]["state"] = "UNKNOWN"
    with pytest.raises(ValueError, match="inflight/unknown"):
        trial.history()


@pytest.mark.parametrize(
    "field,value",
    [("hard_cap_microcny", 900_000_000), ("request_cap", 999999), ("run_id", "replacement-run")],
)
def test_new_batch_registration_rejects_drifted_original_cap_or_ledger_identity(
    monkeypatch, field, value
):
    _, connection = history_fixture(monkeypatch, full)
    connection.cfg[field] = value
    with pytest.raises(ValueError, match="original joint budget"):
        full.historical_prefix(Path("synthetic-R4"))


def test_blocked_design_retains_unknown_without_clearing_halt_or_recovering_assessments(
    monkeypatch,
):
    _, connection = history_fixture(monkeypatch, full)
    unknown = connection.rows[-1]
    previous_cost = unknown["settled_microcny"]
    unknown.update(
        state="UNKNOWN",
        usage_json=None,
        settled_microcny=None,
        response_sha256=None,
        reserved_microcny=2_228_224,
    )
    connection.counters.update(
        spent=connection.counters["spent"] - previous_cost, held=2_228_224, unknown=1
    )
    connection.halt = (json.dumps({"reason": "original transport unknown"}),)
    value = full.historical_prefix(Path("synthetic-R4"))
    assert len(value["paid_entries"]) == 14 and len(value["unknown_entries"]) == 1
    assert value["unknown_entries"][0]["reserved_microcny"] == 2_228_224
    assert value["unknown_entries"][0]["settled_microcny"] is None
    assert value["budget_halt"]["reason"] == "original transport unknown"
    assert not value["review_gate"]["admitted"]
    assert value["paid_execution_requires_separate_admission"]
    assert unknown["state"] == "UNKNOWN" and connection.counters["held"] == 2_228_224


def r4_registration(tmp_path, monkeypatch):
    original = old_plan()
    cohort = original["task_ids"][:6]
    cfg = config()
    parent = shared.bound(
        dict(
            budget=cfg,
            allowed_output_limits=cfg["allowed_output_limits"],
            technical_gate={"task_ids": cohort},
            native_zero_support_task_ids=[cohort[0]],
        )
    )
    history = shared.bound(
        dict(
            parent_actual_calls=15,
            budget_counters={"spent": 123_000_001},
            paid_entries=[{"retained": i} for i in range(15)],
        )
    )
    objects, prepared = {}, {}
    originals = [slot for slot in original["inventory"]["slots"] if slot["task_id"] in cohort]
    seal = []
    for slot in originals:
        path = tmp_path / "originals" / (slot["slot_id"] + ".json")
        value = {"turns": [{"usage": {"completion_tokens": 20}}]}
        objects[path] = value
        seal.append(dict(slot=slot, episode_path=str(path), episode_file_sha256=digest(value)))
    objects[trial.ORIGINAL / "generation_seal/record.json"] = {"slots": seal}
    for task_id in cohort:
        bundle = fixture_bundle()
        bundle["task_id"] = task_id
        for index, slot in enumerate(bundle["slots"]):
            slot["slot_id"] = f"old:{task_id}:{index}"
            slot["trajectory"]["task_id"] = task_id
        prepared[task_id] = dict(
            id="prepared-" + task_id,
            bundle=bundle,
            requests=[
                {
                    "messages": [
                        {},
                        {
                            "content": json.dumps(
                                {
                                    "review_only_private_reference": {
                                        "program": "add(120, 0)",
                                        "answer": 120,
                                    }
                                }
                            )
                        },
                    ]
                }
            ],
            old_review_result="NEVER_REUSE_OLD_PASS",
        )
    monkeypatch.setattr(trial, "__file__", str(tmp_path / "empty-source" / "registration.py"))
    monkeypatch.setattr(
        trial.subprocess, "check_output", lambda *args, **kwargs: "new-frozen-commit"
    )
    monkeypatch.setattr(trial, "history", lambda: (parent, history))
    monkeypatch.setattr(trial, "original_protocol", lambda: original)
    monkeypatch.setattr(trial, "checked_prepared", lambda root, task_id: prepared[task_id])
    monkeypatch.setattr(trial, "read_json", lambda path: objects[Path(path)])
    monkeypatch.setattr(trial, "sha", lambda path: digest(objects[Path(path)]))
    monkeypatch.setattr(trial, "runtime_binding", lambda: {"source": "mock"})
    monkeypatch.setattr(
        trial,
        "publish",
        lambda directory, value, filename="record.json": objects.__setitem__(
            Path(directory) / filename, copy.deepcopy(value)
        ),
    )
    plan = trial.register(tmp_path / "new-R4")
    return plan, parent, objects


def test_R4_registers_all_fixed108_new_review_invocations_not_only15_failed_jobs(
    tmp_path, monkeypatch
):
    plan, parent, objects = r4_registration(tmp_path, monkeypatch)
    assert len(plan["jobs"]) == plan["authorized_paid_jobs_this_registration"] == 108
    slot_jobs = [job for job in plan["jobs"] if job["stage"] == "slot"]
    alignment = [job for job in plan["jobs"] if job["stage"] == "alignment"]
    assert len(slot_jobs) == 96 and len(alignment) == 12
    assert Counter((job["task_id"], job["reviewer"]) for job in slot_jobs) == {
        (task, reviewer): 8 for task in plan["task_ids"] for reviewer in (0, 1)
    }
    assert plan["budget"]["historical_spent_microcny"] == 123_000_001
    assert (
        plan["budget"]["hard_cap_microcny"] == 800_000_000
        and plan["budget"]["request_cap"] == 258000
    )
    assert plan["no_previous_pass_reused"] and plan["new_generation_calls"] == 0
    assert (
        not plan["automatic_full_inventory_expansion"]
        and plan["next_route"] == "new_full_probe_authorized"
    )
    assert {shared.episode_id(plan, j) for j in plan["jobs"]}.isdisjoint(
        shared.episode_id(parent, j) for j in plan["jobs"]
    )
    requests = [
        request
        for obj in objects.values()
        if isinstance(obj, dict) and "requests" in obj
        for request in obj["requests"].values()
    ]
    assert len(requests) == 96 and all(
        "NEVER_REUSE_OLD_PASS" not in json.dumps(request["messages"]) for request in requests
    )
    assert trial.run is shared.run


def test_inherited_gate_false_does_not_load_a_key_or_dispatch(tmp_path, monkeypatch):
    gate = shared.bound(dict(protocol_id="R4", admitted=False))
    selected = tmp_path / "gate-blocked"
    gate_path = selected / "technical_gate/record.json"
    monkeypatch.setattr(Path, "exists", lambda path: path == gate_path)
    monkeypatch.setattr(shared, "checked_plan", lambda output: {"id": "R4"})
    monkeypatch.setattr(shared, "Context", lambda *args: SimpleNamespace())
    monkeypatch.setattr(
        shared, "ledger_for", lambda plan: SimpleNamespace(snapshot=lambda: {"spent": 123})
    )
    monkeypatch.setattr(shared, "recover", lambda context: {})
    monkeypatch.setattr(shared, "read_json", lambda path: gate)
    statuses = []
    monkeypatch.setattr(shared, "status", lambda output, value: statuses.append(value))
    asyncio.run(trial.run(selected, "must-not-read.env"))
    assert statuses[-1]["phase"] == "TECHNICAL_GATE_BLOCKED" and statuses[-1]["new_calls"] == 0


def test_R4_reused_runner_stops_after_engineering108_even_when_gate_passes(tmp_path, monkeypatch):
    plan, _, _ = r4_registration(tmp_path, monkeypatch)
    selected = tmp_path / "new-R4"
    prepared_alignments, phases, statuses = [], [], []
    context = SimpleNamespace(
        output=selected, plan=plan, prepare_alignment=prepared_alignments.append
    )
    monkeypatch.setattr(shared, "checked_plan", lambda output: plan)
    monkeypatch.setattr(shared, "Context", lambda *args: context)
    monkeypatch.setattr(
        shared,
        "ledger_for",
        lambda plan: SimpleNamespace(snapshot=lambda: {"remaining_exposure_microcny": 600_000_000}),
    )
    monkeypatch.setattr(shared, "recover", lambda context: {})
    monkeypatch.setattr(shared, "_key", lambda path: "synthetic-key")
    monkeypatch.setenv("DEEPSEEK_API_KEY", "synthetic-only")
    monkeypatch.setattr(shared, "persist", lambda *args: None)
    monkeypatch.setattr(shared, "status", lambda output, value: statuses.append(value))

    async def fake_batch(context, ledger, key, completed, jobs, phase, concurrency):
        phases.append((phase, len(jobs)))
        for job in jobs:
            completed[job["key"]] = dict(
                artifact={"peak_tariff_upper_bound_microcny": 100},
                assessment={
                    "interface_admitted": True,
                    "semantic_consistent": False,
                    "output_truncated": False,
                },
            )
        return []

    monkeypatch.setattr(shared, "run_batch", fake_batch)
    asyncio.run(trial.run(selected, "synthetic.env"))
    assert phases == [("PILOT_SLOT_REVIEW", 96), ("PILOT_ALIGNMENT", 12)]
    assert prepared_alignments == plan["task_ids"]
    assert statuses[-1]["phase"] == "TECHNICAL_COHORT_COMPLETE_NEW_BATCH_NEXT"
    assert statuses[-1]["training_started"] is False
