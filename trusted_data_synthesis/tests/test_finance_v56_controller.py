import errno
from types import SimpleNamespace

import pytest

import finqa_v54_evaluation as evaluation
import finqa_v56_controller as controller


def evidence(tmp_path):
    path = tmp_path / "evidence/record.json"
    evaluation.publish(path, dict(actual_resource_error=True))
    return evaluation.file_binding(path)


def audit(reference, **updates):
    return dict(resume_allowed=True, unknown_calls=0, progress_units=10,
                durable_progress_digest="actual-bound-state", evidence=[reference], **updates)


def test_confirmed_resource_recovery_uses_long_automatic_cooldown_not_permanent_quarantine(tmp_path):
    reference = evidence(tmp_path)
    failure = dict(classification="RETRY_SAFE_RESOURCE", evidence=[reference], reason="actual free shortage")
    decision = controller.failure_decision(failure, audit(reference), previous_units=10,
        no_progress_failures=3, attempt=4)
    assert decision["status"] == "RESOURCE_COOLDOWN"
    assert decision["backoff_seconds"] == 900 and decision["automatic_readmission"] is True
    assert decision["status"] not in controller.TERMINAL_STATES
    assert controller.auto_recovery_policy()["confirmed_resource_failure_max_attempts"] is None


def test_real_durable_progress_resets_no_progress_counter(tmp_path):
    reference = evidence(tmp_path)
    decision = controller.failure_decision(dict(classification="RETRY_SAFE_RESOURCE", evidence=[reference]),
        audit(reference), previous_units=9, no_progress_failures=8, attempt=12)
    assert decision["status"] == "BACKOFF" and decision["no_progress_failures"] == 0
    assert decision["backoff_seconds"] == 300


@pytest.mark.parametrize("classification", ["UNKNOWN_FEEDBACK", "STATE_BINDING_FAILURE", "NUMERICAL_FAILURE", "HARD_PEAK_LIMIT", None])
def test_unrecognized_or_hard_scientific_failures_never_retry(tmp_path, classification):
    reference = evidence(tmp_path)
    decision = controller.failure_decision(dict(classification=classification, evidence=[reference]),
        audit(reference), previous_units=10, no_progress_failures=0, attempt=1)
    assert decision["status"] == "HARD_BLOCKED"


def test_resource_label_cannot_hide_unknown_or_state_regression(tmp_path):
    reference = evidence(tmp_path)
    failure = dict(classification="RETRY_SAFE_RESOURCE", evidence=[reference])
    unknown = audit(reference)
    unknown["unknown_calls"] = 1
    assert controller.failure_decision(failure, unknown, previous_units=10,
        no_progress_failures=0, attempt=1)["status"] == "HARD_BLOCKED"
    assert controller.failure_decision(failure, audit(reference), previous_units=11,
        no_progress_failures=0, attempt=1)["status"] == "HARD_BLOCKED"


def test_io_retry_requires_actual_admitted_errno_and_pre_child_launch_evidence(tmp_path):
    reference = evidence(tmp_path)
    valid = controller.launch_failure_record(OSError(errno.EAGAIN, "spawn temporarily unavailable"))
    assert valid["actual_child_created"] is False and valid["actual_errno"] == errno.EAGAIN
    valid["evidence"] = [reference]
    assert controller.failure_decision(valid, audit(reference), previous_units=10,
        no_progress_failures=0, attempt=1)["status"] == "BACKOFF"
    invalid = dict(valid, actual_errno=errno.EINVAL)
    assert controller.failure_decision(invalid, audit(reference), previous_units=10,
        no_progress_failures=0, attempt=1)["status"] == "HARD_BLOCKED"
    assert controller.launch_failure_record(RuntimeError("OOM"))["classification"] == "HARD_BLOCK"


def test_blocked_branch_propagates_only_to_its_dependents_and_cooldown_reenters(monkeypatch):
    control = controller.Controller.__new__(controller.Controller)
    control.jobs = dict(
        feedback=dict(job_id="feedback", dependencies=[], priority=0, seed=137),
        replay=dict(job_id="replay", dependencies=["feedback"], priority=1, seed=137),
        train=dict(job_id="train", dependencies=["replay"], priority=2, seed=137),
        independent=dict(job_id="independent", dependencies=[], priority=0, seed=251))
    control.job_states = {key: controller._initial_state() for key in control.jobs}
    control.accepted = {}
    control.job_states["feedback"]["status"] = "HARD_BLOCKED"
    control.job_states["independent"].update(status="RESOURCE_COOLDOWN", next_eligible_epoch=100)
    control._block_dependencies()
    assert control.job_states["replay"]["status"] == control.job_states["train"]["status"] == "DEPENDENCY_BLOCKED"
    monkeypatch.setattr(controller.time, "time", lambda: 99)
    assert control.ready() == []
    monkeypatch.setattr(controller.time, "time", lambda: 101)
    assert [job["job_id"] for job in control.ready()] == ["independent"]


@pytest.mark.parametrize("state", ["RUNNING", "DRAINING", "DISPATCHING"])
def test_supervisor_cannot_restart_over_unsettled_worker_lifecycle(state):
    with pytest.raises(ValueError, match="unsettled dispatch"):
        controller._require_empty_settled_journal(dict(active_jobs=[], job_states=dict(job=dict(status=state))))
    with pytest.raises(ValueError, match="active/unobserved"):
        controller._require_empty_settled_journal(dict(active_jobs=[dict(pid=10)], job_states={}))


def test_stop_marker_is_terminal_without_decoding_or_replacing_it(tmp_path):
    assert controller.stop_requested(tmp_path) is False
    (tmp_path / "STOP").touch()
    assert controller.stop_requested(tmp_path) is True


def test_controller_restart_refuses_missing_real_exit_before_any_lease_probe(tmp_path, monkeypatch):
    attempt = tmp_path / "stages/job/attempts/attempt0001"
    evaluation.publish(attempt / "launch/record.json", dict(pid=123, birth="original"))
    value = evaluation.bound(dict(protocol_id="protocol", active_jobs=[], job_states={},
        attempt_history=[dict(directory=str(attempt))]))
    path = tmp_path / "journal/state.json"
    path.parent.mkdir()
    path.write_text(__import__("json").dumps(value))
    monkeypatch.setattr(controller.fcntl, "flock", lambda *args: pytest.fail("lease touched before exit proof"))
    with pytest.raises(FileNotFoundError):
        controller.controller_restart_audit(tmp_path, dict(id="protocol"))


def test_actual_exit_zero_with_transient_acceptance_IO_waits_and_finalizes_without_new_science(tmp_path):
    control = controller.Controller.__new__(controller.Controller)
    control.root, control.protocol, control.accepted, control.explicit_stop = tmp_path, dict(id="protocol"), {}, False
    job = dict(job_id="job", stage="feedback_C05", kind="feedback", seed=137, dependencies=[])
    control.jobs, control.job_states = {"job": job}, {"job": dict(controller._initial_state(), attempts=1, status="RUNNING")}
    stable = control.job_directory(job)
    attempt = stable / "attempts/attempt0001"
    result = evaluation.publish(stable / "result/record.json", dict(status="COMPLETE"))
    evaluation.publish(attempt / "launch/record.json", dict(pid=77, birth="birth"))
    lease = (tmp_path / "lease.lock").open("a")
    child = controller.base.Child(job=job, gpu=0, uuid="uuid", process=SimpleNamespace(pid=77, poll=lambda: 0),
        lease=lease, birth="birth", pidfd=None, directory=stable, started_epoch=0)
    child.attempt, child.attempt_dir, child.durable_before = 1, attempt, dict(progress_units=0)
    control.active = {"job": child}
    control.journal = lambda: None
    def unavailable(_child):
        raise OSError(errno.EIO, "actual temporary result read failure")
    control._validate_result = unavailable
    control.reap()
    assert lease.closed and control.active == {} and control.accepted == {}
    assert control.job_states["job"]["status"] == "AUDIT_IO_WAIT"
    assert evaluation.checked(attempt / "actual_exit/record.json")["returncode"] == 0
    control._validate_result = lambda child: result
    control.job_states["job"]["next_eligible_epoch"] = 0
    control.refresh_deferred_audits()
    assert control.job_states["job"]["status"] == "COMPLETE"
    assert control.accepted["job"]["actual_exit_zero"] is True
    assert control.job_states["job"]["attempts"] == 1


def test_runtime_binding_exception_blocks_only_affected_job_before_dispatch(tmp_path):
    control = controller.Controller.__new__(controller.Controller)
    control.root = tmp_path
    job = dict(job_id="broken", kind="feedback", seed=137, stage="feedback_C05", dependencies=[])
    independent = dict(job, job_id="healthy", seed=251)
    control.jobs = {"broken": job, "healthy": independent}
    control.job_states = {key: controller._initial_state() for key in control.jobs}
    def invalid(_job):
        raise RuntimeError("actual GenerationBindingError-style failure")
    control._audit = invalid
    lease = (tmp_path / "lease.lock").open("a")
    control.launch(job, (dict(index=0, uuid="uuid"), lease, {}))
    assert lease.closed
    assert control.job_states["broken"]["status"] == "HARD_BLOCKED"
    assert control.job_states["healthy"]["status"] == "PENDING"


def test_explicit_orphan_stop_checks_journal_launch_and_current_birth_without_fake_exitcode(tmp_path, monkeypatch):
    active, history = [], []
    for pid in (77, 88):
        job = f"job{pid}"
        directory = tmp_path / job / "attempts/attempt0001"
        evaluation.publish(directory / "launch/record.json", dict(protocol_id="protocol", job=dict(job_id=job),
            attempt=1, pid=pid, birth="old-birth"))
        active.append(dict(job_id=job, attempt=1, pid=pid, birth="old-birth"))
        history.append(dict(job_id=job, attempt=1, directory=str(directory)))
    evaluation.publish(tmp_path / "journal/state.json", dict(protocol_id="protocol", active_jobs=active, attempt_history=history))
    births = {77: "old-birth", 88: "reused-by-unrelated-process"}
    signals = []
    runtime = SimpleNamespace(birth=lambda pid: births.get(pid))
    monkeypatch.setattr(controller, "_same_live_identity", lambda rt, pid, birth: rt.birth(pid) == birth)
    def signal_owned(pid, number):
        signals.append((pid, number))
        births[pid] = None
    monkeypatch.setattr(controller.os, "kill", signal_owned)
    result = controller.stop_orphaned_workers(tmp_path, dict(id="protocol"), runtime)
    assert signals == [(77, controller.signal.SIGTERM)]
    assert result["all_identities_observed_exited"] is True
    assert controller.stop_requested(tmp_path)
    assert all(row["OS_exitcode"] is None and row["OS_exitcode_independently_observed"] is False
               for row in result["workers"])
