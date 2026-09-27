"""Synthetic recovery metadata and mocked launches; no real GPU or model work."""

import copy
import os
from pathlib import Path
from types import SimpleNamespace

import pytest
import run_cross_market_cuda_recovery_20260927 as m


@pytest.fixture
def recovery(monkeypatch, tmp_path):
    monkeypatch.setattr(m.previous, "RAW", tmp_path)
    monkeypatch.setattr(m.previous, "process_identity", lambda pid: None)
    c = m.context()
    original = m.p.record(
        m.previous.evaluation.PROTOCOL_KIND,
        frozen=True,
        scientific_sources={},
        materials={"runtime_binding": m.previous.evaluation.views.binding()},
        physical_budget=dict(worker_start_cap=216, generate_call_cap=157824),
        scheduling=dict(generation_attempts_per_shard=4, scoring_attempts_per_cohort=2),
    )
    c.write(tmp_path / "protocol.json", original)
    budget = dict(counts=dict(worker_start=1, generate_call=1), committed_generation={})
    c.write(tmp_path / "budget/state.json", budget)
    job = m.p.record(
        "cross_market_evaluation_work_unit",
        protocol_id=original["id"],
        key="g",
        work_kind="generate",
    )
    c.write(tmp_path / "jobspecs/g.json", job)
    directory = tmp_path / "control/attempts/g/1"
    for name, value in {
        "reserved": dict(gpu="GPU-synthetic"),
        "launched": dict(pid=999999999, process_identity="old-process"),
        "started": dict(pid=999999999, process_identity="old-process"),
        "outcome": dict(
            status="FATAL", exception_type="ValueError", message=m.MISSING_CUBLAS_MESSAGE
        ),
    }.items():
        c.write(directory / (name + ".json"), value)
    root = Path(m.__file__).resolve().parents[2]

    def committed(command, **kwargs):
        if command == ["git", "rev-parse", "HEAD"]:
            return "synthetic-commit\n"
        assert command[:2] == ["git", "show"]
        return (root / command[2].split(":", 1)[1]).read_bytes()

    monkeypatch.setattr(m.subprocess, "check_output", committed)
    return c, root, job, original, budget


def test_exact_failure_retry_is_memory_only_and_preserves_protocol_and_budget(recovery):
    c, root, job, original, budget = recovery
    path = c.RAW / "control/attempts/g/1/outcome.json"
    old_failure = path.read_bytes()
    old_protocol = (c.RAW / "protocol.json").read_bytes()
    plan = m.register(root)
    assert m.protocol(root) == plan == m.register(root)
    assert plan["physical_budget"] == original["physical_budget"]
    assert plan["scheduling"] == original["scheduling"]
    assert plan["registered_budget_snapshot"] == budget
    namespace = m.controller_namespace(plan)
    assert namespace["coordinate"].__code__ is m.previous.coordinate.__code__
    assert namespace["worker"].__code__ is m.previous.worker.__code__
    assert namespace["os"].fsync is os.fsync
    assert namespace["attempts"](c, job)[0]["outcome"]["status"] == "RESOURCE_RETRY"
    assert m.previous.attempts(c, job)[0]["outcome"]["status"] == "FATAL"
    assert path.read_bytes() == old_failure
    assert (c.RAW / "protocol.json").read_bytes() == old_protocol
    assert c._budget_state() == budget


@pytest.mark.parametrize("change", ["scoring", "other_error", "new_attempt", "live_worker"])
def test_no_broader_fatal_reclassification(recovery, monkeypatch, change):
    c, root, job, _, _ = recovery
    plan = m.register(root)
    namespace = m.controller_namespace(plan)
    rows = copy.deepcopy(m.previous.attempts(c, job))
    if change == "scoring":
        job = {**job, "work_kind": "score"}
    elif change == "other_error":
        rows[0]["outcome"]["message"] += " different failure"
    elif change == "new_attempt":
        rows[0]["attempt"] = 2
    else:
        rows[0]["alive"] = True
    monkeypatch.setattr(m.previous, "attempts", lambda *args: rows)
    if change == "live_worker":
        with pytest.raises(ValueError, match="exact_registered_failure"):
            namespace["attempts"](c, job)
    else:
        assert namespace["attempts"](c, job)[0]["outcome"]["status"] == "FATAL"


def test_launch_uses_new_script_real_child_environment_and_original_precharge(
    recovery, monkeypatch
):
    c, root, job, _, budget = recovery
    plan = m.register(root)
    launches = []

    def popen(command, **kwargs):
        launches.append((command, kwargs))
        return SimpleNamespace(pid=999999999)

    monkeypatch.setattr(m.previous.subprocess, "Popen", popen)
    m.controller_namespace(plan)["launch"](c, root, job, 2, "GPU-synthetic")
    command, options = launches[0]
    assert command[1] == str(root / m.SCRIPT)
    assert command[2] == "worker"
    assert options["env"]["CUBLAS_WORKSPACE_CONFIG"] == ":4096:8"
    assert options["env"]["CUDA_VISIBLE_DEVICES"] == "GPU-synthetic"
    assert c._budget_state()["counts"] == {
        **budget["counts"],
        "worker_start": budget["counts"]["worker_start"] + 1,
    }
    assert (c.RAW / "budget/intents/worker_start/g/2/process.json").is_file()


def test_direct_worker_without_real_environment_stops_before_generation(recovery, monkeypatch):
    _, root, _, _, _ = recovery
    monkeypatch.delenv("CUBLAS_WORKSPACE_CONFIG", raising=False)

    def forbidden(*args, **kwargs):
        raise AssertionError("worker must reject environment before loading recovery or generation")

    monkeypatch.setattr(m, "protocol", forbidden)
    with pytest.raises(ValueError, match="real_worker_environment_before_generation"):
        m.execute("worker", root, job="synthetic", attempt=2)


def test_mutated_failure_bytes_are_rejected_and_registration_never_resets_commits(recovery):
    c, root, _, _, budget = recovery
    plan = m.register(root)
    ref = plan["allowed_failures"][0]["artifacts"]["outcome"]
    c.write(Path(ref["path"]), dict(status="FATAL", message="different"), immutable=False)
    with pytest.raises(ValueError, match="unchanged_frozen_artifact"):
        m.protocol(root)
    assert c._budget_state() == budget
