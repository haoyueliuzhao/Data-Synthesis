"""Only CPU/memory-ledger/temporary-files tests; no real register, API or GPU."""

import asyncio
import copy
from types import SimpleNamespace

import pytest
from test_finance_v13_material_execution import memory_context

from trusted_synthesis.finance_research import v13_material_controller as original
from trusted_synthesis.finance_research import v13_runtime_c16 as runtime


def authority(ctx, old=()):
    return dict(
        original_plan_id=ctx.plan["id"],
        effective_max_concurrency=16,
        baseline=dict(
            attempted=[dict(episode_id=eid) for eid in old],
            unsent_episode_ids=[j["episode_id"] for j in ctx.jobs if j["episode_id"] not in old],
        ),
    )


def prepared(tmp_path, monkeypatch, count=64):
    ctx, ledger, provider = memory_context(
        tmp_path, monkeypatch, {"projection": count // 2, "mapping": count // 2}
    )
    monkeypatch.setattr(runtime, "_provider", lambda: provider)
    monkeypatch.setattr(runtime, "explicit_proxy", lambda plan: "http://127.0.0.1:7897")
    return ctx, ledger, provider


def test_fixed16_never_mutates_original64_plan_and_resumes_old_settled_without_HTTP(
    tmp_path, monkeypatch
):
    ctx, ledger, provider = prepared(tmp_path, monkeypatch)
    prefix = SimpleNamespace(**ctx.__dict__)
    prefix.jobs = ctx.jobs[:4]
    old = asyncio.run(original.execute_material(prefix, ledger, api_key="CPU-only"))
    original_plan = copy.deepcopy(ctx.plan)
    record = authority(ctx, old)
    result = asyncio.run(runtime.execute_c16(ctx, ledger, runtime=record, api_key="CPU-only"))
    assert len(result) == len(provider.calls) == 64 and provider.maximum == 16
    assert ctx.plan == original_plan and ctx.plan["concurrency"]["max"] == 64
    assert ctx.progress["registered_concurrency_ceiling"] == 16
    assert (
        asyncio.run(runtime.execute_c16(ctx, ledger, runtime=record, api_key="CPU-only")) == result
    )
    assert len(provider.calls) == 64


def test_original_unsent_whitelist_and_runtime_binding_fail_before_send(tmp_path, monkeypatch):
    ctx, ledger, provider = prepared(tmp_path, monkeypatch, count=4)
    record = authority(ctx)
    record["baseline"]["unsent_episode_ids"].pop()
    with pytest.raises(ValueError, match="whitelist"):
        asyncio.run(runtime.execute_c16(ctx, ledger, runtime=record, api_key="CPU-only"))
    assert not provider.calls
    record = authority(ctx)
    record["effective_max_concurrency"] = 64
    with pytest.raises(ValueError, match="concurrency-16"):
        asyncio.run(runtime.execute_c16(ctx, ledger, runtime=record, api_key="CPU-only"))
    assert not provider.calls


def test_samewave_three_unknowns_drain_hold_save_and_no_automatic_retry(tmp_path, monkeypatch):
    ctx, ledger, provider = prepared(tmp_path, monkeypatch, count=32)
    provider.failures.update({j["episode_id"]: "network" for j in ctx.jobs[:3]})
    assert (
        asyncio.run(runtime.execute_c16(ctx, ledger, runtime=authority(ctx), api_key="CPU-only"))
        is None
    )
    assert ctx.progress["phase"] == "NETWORK_SAFETY_SAVED"
    assert len(provider.calls) == 16 and ledger.snapshot()["pending_requests"] == 0
    assert len(ledger.acks) == 3 and ledger.snapshot()["exposure_microcny"] == 300


def test_supervisor_replaces_only_API_child_and_diagnostics_redact(monkeypatch):
    seen = []
    monkeypatch.setattr(
        runtime.OriginalSupervisor, "plain_job", lambda self, job, phase: seen.append((job, phase))
    )
    instance = object.__new__(runtime.Supervisor)
    instance.output = "/CPU-only/output"
    old = dict(
        key="fixed-material-measurements",
        module="v13_material_controller",
        args=["--output", instance.output],
    )
    runtime.Supervisor.plain_job(instance, old, "API")
    assert old["module"] == "v13_material_controller"
    assert seen[0][0]["module"] == "v13_runtime_c16" and seen[0][0]["args"][0] == "api"
    later = dict(key="whole-material", module="v13_workflow", args=["material"])
    runtime.Supervisor.plain_job(instance, later, "MATERIAL")
    assert seen[1][0] is later
    error = RuntimeError("outer")
    error.__cause__ = RuntimeError("CPU_SECRET http://user:credential@proxy.invalid/ " + "x" * 600)
    diagnostic = runtime.cause_diagnostic(error, "CPU_SECRET")
    assert "CPU_SECRET" not in diagnostic["message"] and "credential" not in diagnostic["message"]
    assert len(diagnostic["message"]) == 512 and diagnostic["truncated"]


def test_register_exact_baseline_without_touching_wallet(tmp_path, monkeypatch):
    (tmp_path / "workflow").mkdir()
    plan = dict(
        id="CPU-plan",
        protocol_identity="CPU-protocol",
        source_bindings={"old": "same"},
        concurrency={"max": 64},
    )
    stop = dict(
        id=runtime.STOP_ID,
        source_plan={"id": plan["id"]},
        original_workflow_alive=False,
        financial_halt=False,
        attempted=288,
        network_unknowns=8,
        unsent=1028,
        returned=280,
    )
    baseline = dict(
        attempted=[
            dict(episode_id=str(i), state="SETTLED" if i < 280 else "UNKNOWN") for i in range(288)
        ],
        unknowns=[dict(kind="mapping") for _ in range(8)],
        unsent_episode_ids=[str(i) for i in range(288, 1316)],
    )
    monkeypatch.setattr(runtime, "checked_plan", lambda output: plan)
    monkeypatch.setattr(runtime, "checked", lambda path: stop)
    monkeypatch.setattr(runtime, "observe_wallet", lambda actual_plan: baseline)
    monkeypatch.setattr(
        runtime,
        "entry",
        lambda path: {
            "id": stop["id"] if "report_stop_01" in str(path) else plan["id"],
            "path": str(path),
        },
    )
    record = runtime.register_runtime(tmp_path)
    assert record["baseline"] == baseline and record["effective_max_concurrency"] == 16
    assert not record["new_budget_permit"] and record["new_calls_authorized_max"] == 1028
    assert (tmp_path / "runtime_c16_01/registration/record.json").is_file()
