"""Operational overlays and synthetic CUDA capacity; never launches real models."""

import copy
from pathlib import Path
from types import SimpleNamespace

import pytest
import run_cross_market_performance_20260927 as m


@pytest.fixture
def registered(monkeypatch, tmp_path):
    monkeypatch.setattr(m.previous, "RAW", tmp_path)
    monkeypatch.setattr(
        m.previous, "process_identity", lambda pid: "live" if pid == 12345 else None
    )
    c = m.context()
    original = m.p.record(
        m.previous.evaluation.PROTOCOL_KIND,
        frozen=True,
        scientific_sources={},
        materials={"runtime_binding": m.previous.evaluation.views.binding()},
        physical_budget=dict(worker_start_cap=216, generate_call_cap=157824),
        scheduling=dict(minimum_free_MiB=49152, generation_attempts_per_shard=4),
    )
    c.write(tmp_path / "protocol.json", original)
    c.write(
        tmp_path / "budget/state.json", dict(counts=dict(worker_start=1), committed_generation={})
    )
    job = m.p.record(
        "cross_market_evaluation_work_unit",
        protocol_id=original["id"],
        key="g",
        work_kind="generate",
    )
    c.write(tmp_path / "jobspecs/g.json", job)
    for name, value in {
        "reserved": dict(gpu="GPU-synthetic"),
        "started": dict(pid=999999999, process_identity="old-process"),
        "outcome": dict(
            status="FATAL", exception_type="ValueError", message=m.recovery.MISSING_CUBLAS_MESSAGE
        ),
    }.items():
        c.write(tmp_path / "control/attempts/g/1" / (name + ".json"), value)
    root = Path(m.__file__).resolve().parents[2]

    def committed(command, **kwargs):
        if command == ["git", "rev-parse", "HEAD"]:
            return "synthetic-commit\n"
        assert command[:2] == ["git", "show"]
        return (root / command[2].split(":", 1)[1]).read_bytes()

    monkeypatch.setattr(m.subprocess, "check_output", committed)
    recovered = m.recovery.register(root)
    # Register the operational overlay with an original worker still running.
    c.write(tmp_path / "control/attempts/g/2/reserved.json", dict(gpu="GPU-synthetic"))
    c.write(
        tmp_path / "control/attempts/g/2/started.json", dict(pid=12345, process_identity="live")
    )
    state = dict(
        counts=dict(worker_start=2, generate_call=1), committed_generation={"done": {"calls": 1}}
    )
    c.write(tmp_path / "budget/state.json", state, immutable=False)
    return c, root, job, original, recovered, state


def test_live_transition_retains_real_scientific_record_budget_and_failure_scope(registered):
    c, root, job, original, recovered, state = registered
    old_protocol = (c.RAW / "protocol.json").read_bytes()
    old_outcome = (c.RAW / "control/attempts/g/1/outcome.json").read_bytes()
    plan = m.register(root)
    assert plan["logprob_optimization"] == {"enabled": False}
    assert m.protocol(root) == plan == m.register(root)
    assert len(plan["inherited_active_workers"]) == 1
    assert plan["inherited_active_workers"][0]["attempt"] == 2
    namespace = m.controller_namespace(plan, recovered)
    adapted = namespace["evaluation"].Context(c.RAW)
    assert adapted.read_protocol(root) == original
    assert adapted.read_protocol(root)["scheduling"]["minimum_free_MiB"] == 49152
    m.p.checked(adapted.read_protocol(root), m.previous.evaluation.PROTOCOL_KIND)
    assert namespace["coordinate"].__code__ is m.previous.coordinate.__code__
    assert namespace["worker"].__code__ is m.previous.worker.__code__
    rows = namespace["attempts"](c, job)
    assert rows[0]["outcome"]["status"] == "RESOURCE_RETRY"
    assert rows[1]["alive"] is True
    assert (c.RAW / "protocol.json").read_bytes() == old_protocol
    assert (c.RAW / "control/attempts/g/1/outcome.json").read_bytes() == old_outcome
    assert c._budget_state() == state


def benchmark(c, passed=True):
    helper = m.importlib.import_module(m.LOGPROB_MODULE)
    path = c.RAW / "benchmark.json"
    c.write(
        path,
        dict(
            test=dict(passed=passed, bit_exact=True, rng_unchanged=True),
            helper_sha256=m.p.sha(Path(helper.__file__)),
            anchor_decoder_sha256=m.p.sha(Path(m.previous.legacy.old.feedback.__file__)),
            model_calls=0,
            api_calls=0,
        ),
    )
    return path


def test_optional_logprob_overlay_requires_bound_benchmark_and_isolates_decoder(registered):
    c, root, _, _, recovered, _ = registered
    path = benchmark(c)
    original = m.previous.legacy.old.feedback.generate_jobs
    original_decoder = original.__globals__["Decoder"]
    plan = m.register(root, logprob_benchmark=path)
    assert m.protocol(root) == plan
    config = plan["logprob_optimization"]
    assert config["enabled"] is True
    assert config["helper_source"] in plan["sources"]
    adapted = m.controller_namespace(plan, recovered)["evaluation"].Context(c.RAW)
    function = adapted.old.feedback.generate_jobs
    assert function.__code__.co_code == original.__code__.co_code
    assert function.__code__.co_consts == original.__code__.co_consts
    assert function.__globals__["Decoder"] is not original_decoder
    assert function.__globals__["views"] is m.previous.evaluation.views
    assert original.__globals__["Decoder"] is original_decoder
    changed = m.p.read_json(path)
    changed["test"]["bit_exact"] = False
    c.write(path, changed, immutable=False)
    with pytest.raises(ValueError, match="passing_exact_helper_benchmark"):
        m.protocol(root)


def test_failed_benchmark_cannot_register_optional_optimization(registered):
    c, root, _, _, _, _ = registered
    with pytest.raises(ValueError, match="passing_exact_helper_benchmark"):
        m.register(root, logprob_benchmark=benchmark(c, passed=False))
    assert not (c.RAW / m.DIRECTORY / "protocol.json").exists()


def test_new_launch_uses_operational_runner_original_precharge_and_cuda_environment(
    registered, monkeypatch
):
    c, root, job, _, recovered, state = registered
    namespace = m.controller_namespace(m.register(root), recovered)
    requested, launched = [], []
    monkeypatch.setattr(
        m.previous, "available_gpus", lambda minimum: requested.append(minimum) or ["g"]
    )
    assert namespace["available_gpus"](49152) == ["g"]
    assert requested == [49152]

    def popen(command, **kwargs):
        launched.append((command, kwargs))
        return SimpleNamespace(pid=999999999)

    monkeypatch.setattr(m.previous.subprocess, "Popen", popen)
    namespace["launch"](c, root, job, 3, "GPU-synthetic")
    command, kwargs = launched[0]
    assert command[1:3] == [str(root / m.SCRIPT), "worker"]
    assert kwargs["env"]["CUBLAS_WORKSPACE_CONFIG"] == ":4096:8"
    assert kwargs["env"]["CUDA_VISIBLE_DEVICES"] == "GPU-synthetic"
    assert c._budget_state()["counts"] == {**state["counts"], "worker_start": 3}
    assert (c.RAW / "budget/intents/worker_start/g/3/process.json").is_file()


def mock_capacity(monkeypatch, capacities):
    capacities, empty_calls, sleeps = iter(capacities), [], []
    clock = [0.0]
    cuda = m.previous.legacy.torch.cuda
    monkeypatch.setattr(cuda, "empty_cache", lambda: empty_calls.append(True))
    monkeypatch.setattr(cuda, "mem_get_info", lambda: (next(capacities) * 2**20, 80 * 2**30))
    monkeypatch.setattr(cuda, "memory_reserved", lambda: 0)
    monkeypatch.setattr(cuda, "memory_allocated", lambda: 17 * 2**30)
    monkeypatch.setattr(cuda, "max_memory_allocated", lambda: 22 * 2**30)
    monkeypatch.setattr(cuda, "max_memory_reserved", lambda: 24 * 2**30)
    monkeypatch.setattr(m.time, "monotonic", lambda: clock[0])

    def sleep(seconds):
        sleeps.append(seconds)
        clock[0] += seconds

    monkeypatch.setattr(m.time, "sleep", sleep)
    return empty_calls, sleeps


def test_start_and_continue_thresholds_wait_without_new_attempt_or_budget(tmp_path, monkeypatch):
    empty, sleeps = mock_capacity(monkeypatch, [49152, 48000, 49152])
    c = m.PerformanceContext(tmp_path, operational_id="test")
    c.capacity_boundary("generation", 49152)
    assert not list((tmp_path / m.DIRECTORY).glob("telemetry/*/*.json"))
    c.capacity_boundary("generation", 49152)
    assert len(empty) == 3 and sleeps == [10]
    [status] = (tmp_path / m.DIRECTORY).glob("telemetry/*/*.json")
    value = m.p.read_json(status)
    assert value["status"] == "RESUMED"
    assert value["waited_seconds"] == 10
    assert value["minimum_MiB"] == 49152
    assert value["torch_peak_allocated_MiB"] == 22528
    assert value["torch_peak_reserved_MiB"] == 24576
    assert not (tmp_path / "budget").exists()
    assert not (tmp_path / "control/attempts").exists()


def test_continue_timeout_and_start_race_preserve_original_resource_retry(tmp_path, monkeypatch):
    empty, sleeps = mock_capacity(monkeypatch, [49152] + [48000] * 13)
    c = m.PerformanceContext(tmp_path, operational_id="test")
    c.capacity_boundary("generation", 49152)
    with pytest.raises(m.previous.legacy.CapacityWait, match="120.0s"):
        c.capacity_boundary("generation", 49152)
    assert len(empty) == 14 and sleeps == [10] * 12
    [status] = (tmp_path / m.DIRECTORY).glob("telemetry/*/*.json")
    assert m.p.read_json(status)["status"] == "RESOURCE_RETRY"
    _, sleeps = mock_capacity(monkeypatch, [49151])
    c = m.PerformanceContext(tmp_path / "start_race", operational_id="test")
    with pytest.raises(m.previous.legacy.CapacityWait, match="49152 MiB"):
        c.capacity_boundary("generation", 49152)
    assert sleeps == []


def test_periodic_and_exit_telemetry_do_not_reset_peaks(tmp_path, monkeypatch):
    mock_capacity(monkeypatch, [49152] * 17)
    c = m.PerformanceContext(tmp_path, operational_id="test")
    for _ in range(17):
        c.capacity_boundary("generation", 49152)
    [status] = (tmp_path / m.DIRECTORY).glob("telemetry/*/*.json")
    assert m.p.read_json(status)["status"] == "PERIODIC_BOUNDARY"
    c.record_worker_exit(0)
    [exit_path] = (tmp_path / m.DIRECTORY).glob("telemetry/*/worker_exit.json")
    assert m.p.read_json(exit_path)["torch_peak_reserved_MiB"] == 24576


def test_policy_tampering_and_missing_environment_are_rejected(registered, monkeypatch):
    c, root, _, _, _, _ = registered
    plan = m.register(root)
    fields = {
        key: copy.deepcopy(value)
        for key, value in plan.items()
        if key not in {"id", "schema_version"}
    }
    fields["capacity_policy"]["continue_minimum_available_MiB"] = 1
    c.write(
        c.RAW / m.DIRECTORY / "protocol.json", m.p.record(m.PROTOCOL, **fields), immutable=False
    )
    with pytest.raises(ValueError, match="same_frozen_science"):
        m.protocol(root)
    monkeypatch.delenv("CUBLAS_WORKSPACE_CONFIG", raising=False)
    with pytest.raises(ValueError, match="real_worker_environment"):
        m.execute("worker", root, job="not-opened", attempt=3)
