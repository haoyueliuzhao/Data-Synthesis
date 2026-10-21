"""CPU/mock regression for the separate protection control plane."""
from __future__ import annotations

import copy
import os
from types import SimpleNamespace

import pytest

import finqa_v64_binding as binding

binding.source_module("finqa_v63_entry").install_registered_auxiliary()
import finqa_v64_controller as controller


def audit(progress=784, **changes):
    value = dict(resume_allowed=True, unknown_calls=0, progress_units=progress,
                 durable_progress_digest="same-condition-real-prefix", evidence=[])
    return dict(value, **changes)


def maintenance_fixture():
    def state(status, attempt=0, **changes):
        return dict(status=status, attempts=attempt, no_progress_failures=2,
                    next_eligible_epoch=1234.5, progress_units=768 if attempt else 0,
                    durable_progress_digest="old-prefix" if attempt else None, **changes)
    jobs = dict(replay=dict(kind="replay", dependencies=[]),
                distribution=dict(kind="distribution", dependencies=["replay"]),
                train=dict(kind="train", dependencies=["distribution"]),
                unrelated=dict(kind="replay", dependencies=[]))
    history = [dict(job_id="replay", attempt=2, directory="/science/replay/attempts/attempt0002")]
    before = dict(protocol_id="science", active_jobs=[dict(job_id="replay", attempt=2, pid=123, birth="456")],
        job_states=dict(replay=state("RUNNING", 2), distribution=state("PENDING"),
                        train=state("BACKOFF"), unrelated=state("HARD_BLOCKED", reason="numerical failure")),
        accepted={}, attempt_history=history, resource_wait_seconds=100.0, evaluation_registered=False)
    final = copy.deepcopy(before)
    final["active_jobs"] = []
    final["resource_wait_seconds"] = 105.0
    final["job_states"]["replay"].update(status="HARD_BLOCKED", reason="explicit controller/supervisor stop")
    final["job_states"]["distribution"].update(status="DEPENDENCY_BLOCKED", blocked_by=["replay"])
    final["job_states"]["train"].update(status="DEPENDENCY_BLOCKED", blocked_by=["distribution"])
    proof = dict(attempt=2, pid=123, birth="456", authorization_id="authorization",
        launch="launch", actual_exit="exit", resume_audit="audit", maintenance_acceptance="acceptance")
    refs = dict(
        launch=dict(protocol_id="science", job=dict(job_id="replay"), attempt=2, pid=123, birth="456"),
        exit=dict(protocol_id="science", job_id="replay", attempt=2, pid=123, birth="456",
                  actual_waitpid_observed=True, returncode=1),
        audit=audit(),
        acceptance=dict(status="PASS", authorization_id="authorization", job_id="replay", attempt=2,
            pid=123, birth="456", worker_signaled=True, checkpoint_boundary="complete_response", error_type="ReplayPaused"))
    prepared = dict(maintenance_resume_jobs=dict(replay=proof))
    protocol = dict(scientific_protocol_id="science", maintenance_authorization=dict(id="authorization"))
    return final, before, prepared, protocol, jobs, refs


def restore(fixture):
    final, before, prepared, protocol, jobs, refs = fixture
    return controller.maintenance_states(final, before, prepared, protocol, jobs, audit_reader=refs.__getitem__)


def test_exact_maintenance_restores_prefix_and_only_newly_blocked_dependencies():
    fixture = maintenance_fixture()
    final, before, *_ = fixture
    originals = copy.deepcopy((final, before))
    states = restore(fixture)
    assert states["replay"]["status"] == "PENDING"
    assert states["replay"]["progress_units"] == 784
    assert states["replay"]["attempts"] == 2
    assert states["replay"]["no_progress_failures"] == 2
    assert states["replay"]["next_eligible_epoch"] == 1234.5
    assert states["distribution"]["status"] == "PENDING"
    assert states["train"]["status"] == "BACKOFF"
    assert states["train"]["next_eligible_epoch"] == 1234.5
    assert states["unrelated"] == before["job_states"]["unrelated"]
    assert (final, before) == originals


@pytest.mark.parametrize("change", ["numeric", "wrong_auth", "wrong_pid", "wrong_attempt",
                                   "unknown", "regression", "no_signal", "wrong_boundary",
                                   "not_observed", "wrong_phase", "new_attempt", "resource_reset"])
def test_maintenance_rejects_unsafe_or_unregistered_exceptions(change):
    fixture = maintenance_fixture()
    final, before, prepared, protocol, jobs, refs = fixture
    if change == "numeric":
        refs["acceptance"]["error_type"] = "NumericalFailure"
    elif change == "wrong_auth":
        prepared["maintenance_resume_jobs"]["replay"]["authorization_id"] = "foreign"
    elif change == "wrong_pid":
        before["active_jobs"][0]["pid"] = 124
    elif change == "wrong_attempt":
        prepared["maintenance_resume_jobs"]["replay"]["attempt"] = 3
    elif change == "unknown":
        refs["audit"]["unknown_calls"] = 1
    elif change == "regression":
        refs["audit"]["progress_units"] = 767
    elif change == "no_signal":
        refs["acceptance"]["worker_signaled"] = False
    elif change == "wrong_boundary":
        refs["acceptance"]["checkpoint_boundary"] = "partial_response"
    elif change == "not_observed":
        refs["exit"]["actual_waitpid_observed"] = False
    elif change == "wrong_phase":
        jobs["replay"]["kind"] = "feedback"
    elif change == "new_attempt":
        final["attempt_history"].append(dict(job_id="new", attempt=1, directory="/new"))
    else:
        final["resource_wait_seconds"] = 99.0
    with pytest.raises(ValueError):
        restore(fixture)


def test_existing_hard_block_and_dependency_block_are_not_unlocked():
    fixture = maintenance_fixture()
    final, before, *_ = fixture
    before["job_states"]["distribution"].update(status="DEPENDENCY_BLOCKED", blocked_by=["unrelated"])
    final["job_states"]["distribution"] = copy.deepcopy(before["job_states"]["distribution"])
    before["job_states"]["train"].update(status="DEPENDENCY_BLOCKED", blocked_by=["distribution"])
    states = restore(fixture)
    assert states["distribution"] == final["job_states"]["distribution"]
    assert states["train"] == final["job_states"]["train"]


def test_unrelated_hard_failure_cannot_claim_maintenance():
    fixture = maintenance_fixture()
    fixture[0]["job_states"]["replay"]["reason"] = "state binding mismatch"
    with pytest.raises(ValueError, match="unrelated hard block"):
        restore(fixture)


def test_successful_old_worker_is_inherited_without_maintenance_retry():
    fixture = maintenance_fixture()
    final, before, prepared, *_ = fixture
    prepared["maintenance_resume_jobs"] = {}
    final["job_states"]["replay"].update(status="COMPLETE", accepted_attempt=2)
    final["accepted"] = dict(replay={"path": "/science/accepted", "sha256": "a" * 64})
    final["job_states"]["distribution"] = copy.deepcopy(before["job_states"]["distribution"])
    final["job_states"]["train"] = copy.deepcopy(before["job_states"]["train"])
    assert restore(fixture)["replay"]["status"] == "COMPLETE"
    prepared["maintenance_resume_jobs"] = maintenance_fixture()[2]["maintenance_resume_jobs"]
    with pytest.raises(ValueError, match="accepted"):
        restore(fixture)


def test_old_stop_stays_terminal_old_root_but_does_not_become_new_stop(tmp_path):
    old = tmp_path / "science"
    new = old / "protection"
    new.mkdir(parents=True)
    (old / "STOP").write_text("old lawful maintenance stop\n")
    assert controller.stop_requested(old)
    assert not controller.stop_requested(new)
    (new / "STOP").write_text("new explicit stop\n")
    assert controller.stop_requested(new)


def test_six_worker_cap_and_same_gpu_exclusion_remain_inherited():
    assert controller.base.MAX_WORKERS == 6
    children = {str(i): SimpleNamespace(gpu=i, lifecycle="DRAINING") for i in range(6)}
    assert not controller.base.can_dispatch(children)
    children["5"].gpu = 0
    with pytest.raises(ValueError, match="one experiment worker"):
        controller.base.can_dispatch(children)


def test_launch_uses_next_scientific_attempt_and_new_entry_only(tmp_path, monkeypatch):
    science, control = tmp_path / "science", tmp_path / "science/protection"
    control.mkdir(parents=True)
    monkeypatch.setattr(controller.base.binding, "ROOT", science)
    monkeypatch.setattr(controller, "execution_pythonpath", lambda root: "/frozen/v64:/frozen/v63")
    monkeypatch.setattr(controller.os, "pidfd_open", lambda pid: (_ for _ in ()).throw(ProcessLookupError()), raising=False)
    job = dict(job_id="seed137.replay_C05", seed=137, stage="replay_C05", kind="replay")
    q = controller.Controller.__new__(controller.Controller)
    q.root, q.control_root = science, control
    q.protocol = dict(id="science-id", cpu_affinity={"7": "0-7"})
    q.control_protocol = dict(id="protection-id")
    q.job_states = {job["job_id"]: dict(controller.inherited._initial_state(), attempts=2)}
    q.attempt_history, q.active = [], {}
    q._audit, q.journal = lambda spec: audit(), lambda: None
    q.runtime = SimpleNamespace(worker_environment=lambda row: {}, birth=lambda pid: "999")
    received = []
    process = SimpleNamespace(pid=123, poll=lambda: None)
    monkeypatch.setattr(controller.subprocess, "Popen", lambda argv, **kw: received.append((argv, kw)) or process)
    lease_path = tmp_path / "lease"
    with lease_path.open("w+") as lease:
        q.launch(job, (dict(index=7, uuid="GPU-seven"), lease, dict(actual_admission=True)))
        command, kwargs = received[0]
        expected = science / "stages/seed137/replay_C05/attempts/attempt0003"
        assert str(control / "implementation/finqa_v64_entry.py") in command
        assert str(expected) in command
        assert kwargs["env"]["V64_CONTROL_PROTOCOL_ID"] == "protection-id"
        assert kwargs["env"]["V63_ATTEMPT_DIR"] == kwargs["env"]["V56_ATTEMPT_DIR"] == str(expected)
        assert kwargs["pass_fds"] == (lease.fileno(),)
        assert q.job_states[job["job_id"]]["attempts"] == 3
        assert q.job_states[job["job_id"]]["status"] == "RUNNING"
        launch = controller.evaluation.checked(expected / "launch/record.json")
        assert launch["protocol_id"] == "science-id" and launch["control_protocol_id"] == "protection-id"


def test_restart_audit_stops_before_any_lease_on_new_stop(tmp_path, monkeypatch):
    (tmp_path / "STOP").write_text("stop\n")
    monkeypatch.setattr(controller.fcntl, "flock", lambda *_: pytest.fail("stop must prevent lease acquisition"))
    with pytest.raises(ValueError, match="terminal"):
        controller.controller_restart_audit(tmp_path, {}, {}, SimpleNamespace())


def test_no_missing_waitpid_exception_is_inherited(tmp_path, monkeypatch):
    science = tmp_path / "science"
    monkeypatch.setattr(controller, "SCIENTIFIC_ROOT", science)
    monkeypatch.setattr(controller.base.binding, "ROOT", science)
    attempt = science / "stages/job/attempts/attempt0001"
    controller.evaluation.publish(attempt / "launch/record.json", dict(protocol_id="p",
        job=dict(job_id="job"), attempt=1, pid=123, birth="456"))
    with pytest.raises(FileNotFoundError):
        controller.audit_attempt_exit(dict(job_id="job", attempt=1, directory=str(attempt)),
                                      dict(id="p"), SimpleNamespace(birth=lambda pid: None))


def test_new_success_needs_actual_protection_policy_but_zero_call_reuse_keeps_old_report(tmp_path, monkeypatch):
    queue = controller.Controller.__new__(controller.Controller)
    queue.control_protocol = dict(id="new", memory_protection_policy={"cache": "native"})
    queue.protocol = dict(id="original")
    child = SimpleNamespace(attempt_dir=tmp_path, job=dict(job_id="job"), gpu=7)
    result = dict(resources={})
    monkeypatch.setattr(controller.inherited.Controller, "_validate_result", lambda self, value: result)
    with pytest.raises(ValueError, match="actual registered protection"):
        queue._validate_result(child)
    result["resources"].update(control_protocol_id="new", resource_protection=dict(
        policy={"cache": "native"}, future_capacity_or_exclusivity_guaranteed=False,
        warm_attempted=False, receipt=None))
    assert queue._validate_result(child) is result
    result["resources"]["resource_protection"]["warm_attempted"] = True
    with pytest.raises(ValueError, match="immutable actual receipt"):
        queue._validate_result(child)
    (tmp_path / "reused_result").mkdir()
    (tmp_path / "reused_result/record.json").write_text("already validated by inherited zero-call proof\n")
    result["resources"] = {"original_resource_report": True}
    assert queue._validate_result(child) is result
