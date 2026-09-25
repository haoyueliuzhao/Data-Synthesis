"""Synthetic local CPU control-plane states; no real artifacts, GPU or subprocess."""

import importlib
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parents[1] / "scripts"))
r = importlib.import_module("run_fixed_kernel_direction_reliability_20260926")
c, p = r.c, r.p


def setup(tmp_path, monkeypatch):
    root, raw = tmp_path / "repo", tmp_path / "raw"
    root.mkdir()
    raw.mkdir()
    source = root / "synthetic_source.py"
    source.write_text("frozen = True\n")
    monkeypatch.setattr(c, "RAW", raw)
    monkeypatch.setattr(c.b, "read_protocol", lambda _: {"id": "parent"})
    monkeypatch.setattr(c, "_verified", {})
    inputs = {
        str(seed): dict(
            job_key=f"B_direction_reliability_{seed}",
            required_responses=responses,
            positive_trajectories=positives,
        )
        for seed, responses, positives in ((11, 593, 99), (29, 546, 90), (47, 572, 103))
    }
    plan = p.record(
        "B_direction_reliability_protocol",
        frozen=True,
        parent_B_protocol_id="parent",
        seeds=[11, 29, 47],
        required_responses=1711,
        required_positive_trajectories=292,
        new_feedback_sessions=0,
        new_scoring_cases=0,
        sources={"synthetic_source.py": p.sha(source)},
        reliability_inputs=inputs,
        jobs=[dict(key=inputs[str(seed)]["job_key"], seed=seed) for seed in (11, 29, 47)],
        physical_budget=dict(
            reliability_response=2095,
            worker_start=24,
            optimizer=0,
            population=0,
            generate_call=0,
            score_case=0,
        ),
        extra_responses_per_seed=128,
        maximum_attempts_per_job=8,
        resources=dict(host_free_bytes=128 * 2**30, minimum_disk_free_bytes=100 * 2**30),
    )
    c.write(raw / "protocol.json", plan)
    return root, raw, plan


def state(raw, counts):
    c.write(raw / "budget/state.json", dict(counts=counts, at="synthetic"), immutable=False)


def result(plan, job, **changed):
    source = plan["reliability_inputs"][str(job["seed"])]
    values = dict(
        plan_id=plan["id"],
        job_key=job["key"],
        seed=job["seed"],
        complete=True,
        equivalence_passed=True,
        required_responses=source["required_responses"],
        positive_trajectories=source["positive_trajectories"],
        analysis=dict(
            cross=dict(S_1_to_2=-0.3, S_2_to_1=0.2, interpretable=True),
            half_C_comparison=dict(relative_weighted_RMS=1.2, weighted_cosine=-0.4),
        ),
    )
    values.update(changed)
    return p.record("B_direction_reliability_report", **values)


def completed_seed_files(raw, plan, changed=None):
    for job in plan["jobs"]:
        value = result(plan, job, **(changed or {}) if job["seed"] == 29 else {})
        c.write(raw / "reliability" / job["key"] / "report.json", value)
    state(raw, dict(reliability_response=1711, worker_start=3))


def test_protocol_detects_source_change_before_execution(tmp_path, monkeypatch):
    root, raw, plan = setup(tmp_path, monkeypatch)
    assert c.read_protocol(root) == plan
    (root / "synthetic_source.py").write_text("frozen = False\n")
    monkeypatch.setattr(r.worker, "run", lambda *args: pytest.fail("GPU worker called"))
    assert r.run_worker(root, 11, 1, 0) == 1
    value = p.read_json(raw / "results/B_direction_reliability_11/0001.json")
    assert "frozen_source" in value["error"] and not value["resource_retry_allowed"]
    assert not (raw / "worker_identities").exists()


@pytest.mark.parametrize(
    "kind", ["optimizer", "population", "generate_call", "score_case", "unknown"]
)
def test_nonregistered_work_has_zero_budget(tmp_path, monkeypatch, kind):
    _, raw, _ = setup(tmp_path, monkeypatch)
    with pytest.raises(ValueError, match="physical_budget_exhausted"):
        c.reserve(kind, "B_direction_reliability_11", 1, 0)
    assert not (raw / "budget/state.json").exists()


def test_global_and_per_seed_response_caps_charge_before_work(tmp_path, monkeypatch):
    _, raw, _ = setup(tmp_path, monkeypatch)
    key = "B_direction_reliability_11"
    state(raw, {"reliability_response": 2094, "reliability_response:" + key: 720})
    c.reserve("reliability_response", key, 8, 592)
    counts = p.read_json(raw / "budget/state.json")["counts"]
    assert counts["reliability_response"] == 2095
    assert counts["reliability_response:" + key] == 593 + 128
    with pytest.raises(ValueError, match="physical_budget_exhausted"):
        c.reserve("reliability_response", "B_direction_reliability_29", 8, 0)
    state(raw, {"reliability_response": 721, "reliability_response:" + key: 721})
    with pytest.raises(ValueError, match="per_seed_replay_cap"):
        c.reserve("reliability_response", key, 8, 593)


def test_duplicate_intent_and_unknown_seed_cannot_bypass_budget(tmp_path, monkeypatch):
    _, raw, _ = setup(tmp_path, monkeypatch)
    key = "B_direction_reliability_29"
    c.reserve("reliability_response", key, 1, 0)
    with pytest.raises(ValueError, match="no_same_attempt"):
        c.reserve("reliability_response", key, 1, 0)
    with pytest.raises(ValueError, match="only_registered_seed"):
        c.reserve("reliability_response", "B_direction_reliability_99", 1, 0)
    assert p.read_json(raw / "budget/state.json")["counts"]["reliability_response"] == 1


def test_counter_first_crash_conservatively_overcharges(tmp_path, monkeypatch):
    _, raw, _ = setup(tmp_path, monkeypatch)
    original = c.write

    def fail_intent(path, value, immutable=True):
        if "intents" in path.parts:
            raise OSError("synthetic intent write interruption")
        return original(path, value, immutable)

    monkeypatch.setattr(c, "write", fail_intent)
    with pytest.raises(OSError, match="interruption"):
        c.reserve("reliability_response", "B_direction_reliability_47", 1, 0)
    assert p.read_json(raw / "budget/state.json")["counts"]["reliability_response"] == 1
    monkeypatch.setattr(c, "write", original)
    c.reserve("reliability_response", "B_direction_reliability_47", 2, 0)
    assert p.read_json(raw / "budget/state.json")["counts"]["reliability_response"] == 2


def test_worker_start_total_budget_is_finite(tmp_path, monkeypatch):
    _, raw, _ = setup(tmp_path, monkeypatch)
    state(raw, dict(worker_start=23))
    c.reserve("worker_start", "B_direction_reliability_47", 8, 0)
    with pytest.raises(ValueError, match="physical_budget_exhausted"):
        c.reserve("worker_start", "B_direction_reliability_11", 9, 0)


def test_input_hash_verified_once_per_unchanged_file_and_rechecked_after_change(
    tmp_path, monkeypatch
):
    _, raw, _ = setup(tmp_path, monkeypatch)
    oldraw = tmp_path / "old_B"
    oldraw.mkdir()
    monkeypatch.setattr(c.b, "RAW", oldraw)
    path = oldraw / "population.pt"
    path.write_bytes(b"synthetic numeric fixture")
    plan = dict(reliability_inputs={"11": dict(files=dict(population=r.input_ref(path)))})
    original_sha, calls = p.sha, []

    def digest(value):
        if isinstance(value, Path):
            calls.append(value)
        return original_sha(value)

    monkeypatch.setattr(p, "sha", digest)
    assert c.require_input(plan, 11, "population") == path
    assert c.require_input(plan, 11, "population") == path
    assert calls == [path]
    path.write_bytes(b"changed synthetic numeric fixture")
    with pytest.raises(ValueError, match="frozen_input_bytes"):
        c.require_input(plan, 11, "population")
    outside = raw / "outside.pt"
    outside.write_bytes(b"fixture")
    plan["reliability_inputs"]["11"]["files"]["population"] = r.input_ref(outside)
    with pytest.raises(ValueError, match="original_B_input"):
        c.require_input(plan, 11, "population")


@pytest.mark.parametrize(
    "exception,code",
    [
        (MemoryError("host"), 42),
        (c.torch.OutOfMemoryError("GPU"), 42),
        (c.CapacityWait("headroom"), 43),
        (ValueError("numeric"), 1),
    ],
)
def test_only_resource_worker_failures_are_retriable(tmp_path, monkeypatch, exception, code):
    root, raw, _ = setup(tmp_path, monkeypatch)
    monkeypatch.setattr(r.identity, "identity", lambda _: dict(pid=999, command=["synthetic"]))

    def failed_worker(*args):
        raise exception

    monkeypatch.setattr(r.worker, "run", failed_worker)
    assert r.run_worker(root, 29, 1, 0) == code
    value = p.read_json(raw / "results/B_direction_reliability_29/0001.json")
    assert value["returncode"] == code and "finished_at" in value
    if code == 1:
        assert not value["resource_retry_allowed"]


def test_successful_finish_binds_all_three_and_keeps_negative_cross_score(tmp_path, monkeypatch):
    root, raw, plan = setup(tmp_path, monkeypatch)
    completed_seed_files(raw, plan)
    published = []
    monkeypatch.setattr(r, "publish", lambda root, report: published.append(report) or True)
    assert r.finish(root, plan)
    final = p.checked(p.read_json(raw / "complete.json"), "B_direction_reliability_completed")
    assert final["protocol_id"] == plan["id"]
    assert [row["seed"] for row in final["seeds"]] == [11, 29, 47]
    assert sum(row["responses"] for row in final["seeds"]) == 1711
    assert sum(row["positive_trajectories"] for row in final["seeds"]) == 292
    assert all(row["cross"]["S_1_to_2"] == -0.3 for row in final["seeds"])
    assert final["no_selection_or_algorithm_change"] and len(published) == 1


@pytest.mark.parametrize(
    "changed",
    [
        dict(seed=11),
        dict(job_key="B_direction_reliability_11"),
        dict(required_responses=593),
        dict(positive_trajectories=99),
        dict(equivalence_passed=False),
        dict(plan_id="different"),
    ],
)
def test_finish_rejects_copied_or_mismatched_seed_result(tmp_path, monkeypatch, changed):
    root, raw, plan = setup(tmp_path, monkeypatch)
    completed_seed_files(raw, plan, changed)
    monkeypatch.setattr(
        r, "publish", lambda *args: pytest.fail("published mismatched scientific result")
    )
    with pytest.raises(ValueError, match="direction"):
        r.finish(root, plan)
    assert not (raw / "complete.json").exists()


def test_finish_rejects_existing_aggregate_for_another_protocol(tmp_path, monkeypatch):
    root, raw, plan = setup(tmp_path, monkeypatch)
    report = p.record(
        "B_direction_reliability_completed",
        protocol_id="wrong",
        complete=True,
        status="COMPLETE_SAME_POINT_MECHANISM_DIAGNOSTIC",
    )
    c.write(raw / "report.json", report)
    monkeypatch.setattr(r, "publish", lambda *args: pytest.fail("published foreign aggregate"))
    with pytest.raises(ValueError, match="direction"):
        r.finish(root, plan)


def test_publication_retry_reuses_identical_scientific_report_without_new_work(
    tmp_path, monkeypatch
):
    root, raw, plan = setup(tmp_path, monkeypatch)
    completed_seed_files(raw, plan)
    seen = []

    def publish(root, report):
        seen.append(report["id"])
        return len(seen) == 2

    monkeypatch.setattr(r, "publish", publish)
    monkeypatch.setattr(
        c, "reserve", lambda *args: pytest.fail("new scientific work while publishing")
    )
    assert not r.finish(root, plan)
    assert not (raw / "complete.json").exists()
    assert r.finish(root, plan)
    assert len(set(seen)) == 1


class EndOneLoop(BaseException):
    pass


def test_adopts_live_worker_without_new_spawn_and_preserves_GPU(tmp_path, monkeypatch):
    root, raw, plan = setup(tmp_path, monkeypatch)
    key = plan["jobs"][0]["key"]
    process = dict(pid=101, command=["synthetic"])
    row = dict(key=key, seed=11, attempt=2, identity=process)
    control = dict(jobs={}, active={key: {**row, "gpu": dict(index=7, uuid="GPU-synthetic")}})
    c.write(raw / "control/state.json", control)
    c.write(raw / "worker_identities" / key / "0002.json", row)
    monkeypatch.setattr(r.identity, "identity", lambda _: dict(pid=999))
    monkeypatch.setattr(r.identity, "same_process", lambda value: value["pid"] == 101)
    monkeypatch.setattr(c.old, "host_memory", lambda: dict(MemAvailable_bytes=0))
    monkeypatch.setattr(r, "spawn", lambda *args, **kwargs: pytest.fail("duplicate adopted worker"))

    def stop(_):
        raise EndOneLoop()

    monkeypatch.setattr(r.time, "sleep", stop)
    with pytest.raises(EndOneLoop):
        r.coordinate(root)
    saved = p.read_json(raw / "control/state.json")
    assert saved["active"][key]["identity"] == process
    assert saved["active"][key]["gpu"]["index"] == 7
    assert saved["jobs"][key]["attempt"] == 2


def test_numeric_failed_worker_stops_dispatch_and_fails_closed(tmp_path, monkeypatch):
    root, raw, plan = setup(tmp_path, monkeypatch)
    key = plan["jobs"][0]["key"]
    row = dict(key=key, seed=11, attempt=1, identity=dict(pid=101))
    c.write(raw / "control/state.json", dict(jobs={}, active={key: row}))
    c.write(raw / "results" / key / "0001.json", dict(returncode=1, error="numeric linkage"))
    monkeypatch.setattr(r.identity, "identity", lambda _: dict(pid=999))
    monkeypatch.setattr(r.identity, "same_process", lambda _: False)
    monkeypatch.setattr(r, "finish", lambda *args: pytest.fail("completed after numeric failure"))
    monkeypatch.setattr(
        r, "spawn", lambda *args, **kwargs: pytest.fail("continued after numeric failure")
    )
    assert r.coordinate(root) == 1
    saved = p.read_json(raw / "control/state.json")
    assert not saved["active"] and saved["jobs"][key]["stopped"]["returncode"] == 1


def test_resource_failed_worker_preserves_attempt_and_waits_for_retry(tmp_path, monkeypatch):
    root, raw, plan = setup(tmp_path, monkeypatch)
    key = plan["jobs"][0]["key"]
    row = dict(key=key, seed=11, attempt=2, identity=dict(pid=101))
    status = dict(attempt=2, failures=0, not_before=0, stopped=None)
    c.write(raw / "control/state.json", dict(jobs={key: status}, active={key: row}))
    c.write(raw / "results" / key / "0002.json", dict(returncode=42, error="synthetic OOM"))
    monkeypatch.setattr(r.identity, "identity", lambda _: dict(pid=999))
    monkeypatch.setattr(r.identity, "same_process", lambda _: False)
    monkeypatch.setattr(r, "finish", lambda *args: False)
    monkeypatch.setattr(c.old, "host_memory", lambda: dict(MemAvailable_bytes=0))
    monkeypatch.setattr(r.time, "time", lambda: 1000)
    monkeypatch.setattr(r, "spawn", lambda *args, **kwargs: pytest.fail("no resources admitted"))

    def stop(_):
        raise EndOneLoop()

    monkeypatch.setattr(r.time, "sleep", stop)
    with pytest.raises(EndOneLoop):
        r.coordinate(root)
    saved = p.read_json(raw / "control/state.json")
    assert not saved["active"]
    assert saved["jobs"][key] == dict(attempt=2, failures=1, not_before=1120, stopped=None)
