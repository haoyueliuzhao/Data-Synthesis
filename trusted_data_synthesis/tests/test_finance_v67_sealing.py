"""CPU-only known-envelope repair: original failure remains immutable."""
from copy import deepcopy
import fcntl
import json
import os
from pathlib import Path
from types import SimpleNamespace

import pytest

import finqa_v67_binding as binding
import finqa_v67_sealing as sealing


def rewrite(path, body):
    body = {key: value for key, value in body.items() if key != "id"}
    value = dict(**body, id=binding.digest(body))
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value))
    return value


class Episode:
    def __init__(self, value):
        self.value = value

    def model_dump(self, *, mode):
        assert mode == "json"
        return self.value


@pytest.fixture
def repaired_source(tmp_path, monkeypatch):
    root, old = tmp_path / "evaluation_completion_01", tmp_path / "early_generation_01"
    monkeypatch.setattr(binding, "ROOT", root)
    monkeypatch.setattr(binding, "SOURCE_GENERATION_ROOT", old)
    monkeypatch.setenv("CUDA_VISIBLE_DEVICES", "")
    jobid = "original_known_job"
    job = dict(job_id=jobid, stage="generate", feedback_batch=1, panel="calibration120",
        role="calibration", config=dict(seed=11), model_identity=dict(point_id="original-scientific-point"),
        checkpoint=dict(path="/original/checkpoint", state_sha256="a" * 64), denominator=2)
    directory = old / "evaluations/jobs" / jobid
    generation = directory / "shards/calibration120/generation"
    attempt = directory / "attempts/attempt0001"
    directory.mkdir(parents=True)
    (directory / "worker.lock").touch()
    oldprotocol = rewrite(old / "protocol/record.json", dict(scientific_protocol_id="science-id"))
    plan = rewrite(old / "evaluations/registration/record.json", dict(
        protocol_id=oldprotocol["id"], scientific_protocol_id="science-id", jobs={jobid: job},
        runtime_binding={"public": "frozen"}, snapshot_id="same-public-snapshot",
        cohorts=dict(calibration=dict(tasks=["task-a", "task-b"]))))
    monkeypatch.setattr(sealing, "_checked_plan", lambda: (oldprotocol, plan))
    monkeypatch.setattr(sealing, "_same_live_identity", lambda *_: False)
    launch = rewrite(attempt / "launch/record.json", dict(protocol_id=oldprotocol["id"],
        attempt=1, job=job, pid=12345678, birth="old-birth"))
    rewrite(attempt / "actual_exit/record.json", dict(protocol_id=oldprotocol["id"],
        attempt=1, job_id=jobid, pid=launch["pid"], birth=launch["birth"],
        actual_waitpid_observed=True, returncode=1, observed_epoch=3.0))
    resources = dict(all_gates_passed=True, single_process_lifetime_includes_loading=True,
        received_signals=[], observed_violation=None, deferred_observation=None,
        peak_allocated_bytes=20 * sealing.GIB, peak_rss_bytes=24 * sealing.GIB,
        minimum_boundary_free_bytes=8 * sealing.GIB, minimum_host_available_bytes=256 * sealing.GIB)
    closepath = old / f"resources/{jobid}/pid{launch['pid']}/closeout/record.json"
    rewrite(closepath, dict(status="COMPLETE", protocol_id=oldprotocol["id"],
        job_id=jobid, pid=launch["pid"], birth=launch["birth"], resources=resources,
        at="1970-01-01T00:00:01+00:00", error=None))
    failure = rewrite(attempt / "failure/record.json", dict(schema="v63_actual_attempt_failure.v1",
        protocol_id=oldprotocol["id"], job=job, feedback_batch=1, pid=launch["pid"],
        finished_epoch=2.0,
        attempt_root=str(attempt), exception_type="TypeError", error=sealing.KNOWN_ERROR,
        exception_chain=[dict(type="TypeError", module="builtins", actual_errno=None,
            message=sealing.KNOWN_ERROR, automatic_recovery_allowed=None)],
        resources=resources, resource_closeout=binding.entry(closepath)))
    run = rewrite(generation / "run.json", dict(tasks=["task-a", "task-b"],
        config=job["config"], provider=job["model_identity"], role="calibration"))
    seal = rewrite(generation / "generation_seal/seal.json", dict(complete=True,
        all_provider_calls_settled=True, registered_denominator=2, episodes=[{}, {}], run_id=run["id"]))
    episodes = [Episode(dict(final_answer="unchanged-a")), Episode(dict(final_answer="unchanged-b"))]
    native = SimpleNamespace(inspect_shard=lambda *_: dict(completed=2, denominator=2, sealed=True))
    storage = SimpleNamespace(runtime_binding=lambda: plan["runtime_binding"],
        sealed_episodes=lambda _: (run, seal, episodes))
    monkeypatch.setattr(sealing, "_native", lambda: (storage, native))
    # Shared canonical helper's real Episode case is tested in evaluation tests.
    monkeypatch.setattr(sealing, "canonical_episode_hash", lambda episode: binding.digest(episode.model_dump(mode="json")))
    protocol = rewrite(root / "protocol/record.json", dict(scientific_protocol_id="science-id"))
    cpuattempt = root / "repairs" / jobid / "attempt0001"
    rewrite(cpuattempt / "launch/record.json", dict(protocol_id=protocol["id"], job_id=jobid,
        attempt=1, pid=os.getpid(), birth="cpu-birth", cuda_visible_devices=""))
    monkeypatch.setattr(sealing, "_resource_sample", lambda label: dict(label=label,
        observed_epoch=1.0, pid=os.getpid(), host=dict(available_bytes=256 * sealing.GIB),
        rss_bytes=sealing.GIB, peak_rss_bytes=sealing.GIB,
        rss_limit_bytes=sealing.CPU_RSS_LIMIT_BYTES, host_reserve_bytes=sealing.HOST_RESERVE_BYTES,
        CUDA_initialized=False, CUDA_VISIBLE_DEVICES="", passed=True))
    return SimpleNamespace(root=root, old=old, jobid=jobid, job=job, directory=directory,
        generation=generation, attempt=attempt, cpuattempt=cpuattempt, protocol=protocol,
        oldprotocol=oldprotocol, failure=failure, closepath=closepath, native=native, storage=storage)


def source_bytes(e):
    return {str(path.relative_to(e.old)): path.read_bytes() for path in e.old.rglob("*") if path.is_file()}


def test_repair_is_read_only_and_accepts_only_separate_real_cpu_exit(repaired_source):
    e = repaired_source
    before = source_bytes(e)
    assert sealing.eligible_source_job(e.root, e.jobid)["status"] == "ELIGIBLE"
    result = sealing.run_cpu_repair(e.root, e.jobid, e.cpuattempt)
    assert result["original_generation_returncode"] == 1 and result["original_failure_preserved"]
    assert result["actual_new_response_calls"] == result["scoring_calls"] == 0
    assert not (e.root / "adopted" / e.jobid / "accepted/record.json").exists()
    with pytest.raises(FileNotFoundError):
        sealing.accept_cpu_repair(e.root, e.jobid, e.cpuattempt)
    rewrite(e.cpuattempt / "actual_exit/record.json", dict(protocol_id=e.protocol["id"],
        job_id=e.jobid, attempt=1, pid=os.getpid(), birth="cpu-birth", returncode=0,
        actual_waitpid_observed=True))
    accepted = sealing.accept_cpu_repair(e.root, e.jobid, e.cpuattempt)
    assert accepted["cpu_finalization_returncode"] == 0
    assert accepted["original_generation_returncode"] == 1
    assert accepted["new_GPU_exit_required"] is False
    assert before == source_bytes(e)


@pytest.mark.parametrize("change", ["live", "missing_exit", "lock"])
def test_incomplete_or_draining_source_waits_without_writes(repaired_source, monkeypatch, change):
    e = repaired_source
    lock = None
    if change == "live":
        monkeypatch.setattr(sealing, "_same_live_identity", lambda *_: True)
    elif change == "missing_exit":
        (e.attempt / "actual_exit/record.json").unlink()
    else:
        lock = (e.directory / "worker.lock").open("r")
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
    before = source_bytes(e)
    try:
        assert sealing.eligible_source_job(e.root, e.jobid)["status"] == "WAIT"
    finally:
        if lock:
            lock.close()
    assert before == source_bytes(e)
    assert not (e.root / "adopted").exists()


@pytest.mark.parametrize("change", ["error", "extra_cause", "exit_zero", "wrong_birth", "missing_failure",
    "native_incomplete", "unknown", "resource_fail", "signal", "wrong_job", "resource_path", "new_attempt"])
def test_only_exact_post_generation_failure_is_eligible(repaired_source, change):
    e = repaired_source
    if change in ("error", "extra_cause", "resource_path", "wrong_job"):
        failure = deepcopy(e.failure)
        if change == "error":
            failure["error"] = "different TypeError"
        elif change == "extra_cause":
            failure["exception_chain"].append(dict(type="OutOfMemoryError"))
        elif change == "resource_path":
            failure["resource_closeout"]["path"] = "/other/job/record.json"
        else:
            failure["job"]["config"]["seed"] = 29
        rewrite(e.attempt / "failure/record.json", failure)
    elif change in ("exit_zero", "wrong_birth"):
        path = e.attempt / "actual_exit/record.json"
        value = binding.checked(path)
        value["returncode" if change == "exit_zero" else "birth"] = 0 if change == "exit_zero" else "different"
        rewrite(path, value)
    elif change == "missing_failure":
        (e.attempt / "failure/record.json").unlink()
    elif change in ("native_incomplete", "unknown"):
        path = e.generation / "generation_seal/seal.json"
        value = binding.checked(path)
        value["complete" if change == "native_incomplete" else "all_provider_calls_settled"] = False
        rewrite(path, value)
    elif change in ("resource_fail", "signal"):
        value = binding.checked(e.closepath)
        value["resources"]["all_gates_passed" if change == "resource_fail" else "received_signals"] = False if change == "resource_fail" else [15]
        rewrite(e.closepath, value)
        failure = deepcopy(e.failure)
        failure.update(resources=value["resources"], resource_closeout=binding.entry(e.closepath))
        rewrite(e.attempt / "failure/record.json", failure)
    else:
        (e.directory / "attempts/attempt0002").mkdir()
    with pytest.raises((ValueError, FileNotFoundError)):
        sealing.eligible_source_job(e.root, e.jobid)
    assert not (e.root / "adopted").exists()


def test_native_binding_failure_is_not_hidden(repaired_source):
    e = repaired_source
    e.native.inspect_shard = lambda *_: (_ for _ in ()).throw(ValueError("changed Episode identity"))
    before = source_bytes(e)
    with pytest.raises(ValueError, match="changed Episode identity"):
        sealing.run_cpu_repair(e.root, e.jobid, e.cpuattempt)
    assert binding.checked(e.cpuattempt / "failure/record.json")["automatic_retry_authorized"] is False
    assert not (e.root / "adopted" / e.jobid / "result/record.json").exists()
    assert source_bytes(e) == before


def test_cpu_resource_failure_blocks_publication(repaired_source, monkeypatch):
    e = repaired_source
    monkeypatch.setattr(sealing, "_resource_sample", lambda label: dict(label=label, passed=False))
    with pytest.raises(ValueError, match="RSS or effective host"):
        sealing.run_cpu_repair(e.root, e.jobid, e.cpuattempt)
    assert not (e.root / "adopted").exists()


@pytest.mark.parametrize("change", ["nonzero", "birth", "waitpid", "live"])
def test_cpu_result_without_matching_actual_exit_is_not_accepted(repaired_source, monkeypatch, change):
    e = repaired_source
    sealing.run_cpu_repair(e.root, e.jobid, e.cpuattempt)
    value = dict(protocol_id=e.protocol["id"], job_id=e.jobid, attempt=1,
        pid=os.getpid(), birth="cpu-birth", returncode=0, actual_waitpid_observed=True)
    if change == "nonzero":
        value["returncode"] = 1
    elif change == "birth":
        value["birth"] = "other-birth"
    elif change == "waitpid":
        value["actual_waitpid_observed"] = False
    else:
        monkeypatch.setattr(sealing, "_same_live_identity", lambda *_: True)
    rewrite(e.cpuattempt / "actual_exit/record.json", value)
    with pytest.raises(ValueError, match="separately observed"):
        sealing.accept_cpu_repair(e.root, e.jobid, e.cpuattempt)
    assert not (e.root / "adopted" / e.jobid / "accepted/record.json").exists()


def test_cpu_worker_rejects_visible_cuda(repaired_source, monkeypatch):
    e = repaired_source
    monkeypatch.setenv("CUDA_VISIBLE_DEVICES", "0")
    with pytest.raises(ValueError, match="hide every CUDA"):
        sealing.run_cpu_repair(e.root, e.jobid, e.cpuattempt)
