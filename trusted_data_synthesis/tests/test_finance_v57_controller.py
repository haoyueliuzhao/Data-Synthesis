import copy
import errno
from pathlib import Path
from types import SimpleNamespace

import pytest

import finqa_v57_controller as controller

evaluation = controller.evaluation


def setup_attempt(tmp_path, *, attempt=1, with_exit=False):
    root = tmp_path / "science"
    directory = root / "stages/seed251/feedback_C05/attempts" / f"attempt{attempt:04d}"
    row = dict(job_id="seed251.feedback_C05", attempt=attempt, directory=str(directory))
    launch = dict(protocol_id="science", job=dict(job_id=row["job_id"]), attempt=attempt,
                  pid=987654, birth="old-birth")
    evaluation.publish(directory / "launch/record.json", launch)
    observation = tmp_path / "control/identity/record.json"
    if not observation.exists():
        evaluation.publish(observation, dict(all_observed_gone=True))
    allowed = dict(directory=str(directory), launch=evaluation.file_binding(directory / "launch/record.json"),
                   pid=launch["pid"], birth=launch["birth"], identity_exit=evaluation.file_binding(observation),
                   old_returncode=None)
    if with_exit:
        evaluation.publish(directory / "actual_exit/record.json", dict(protocol_id="science",
            job_id=row["job_id"], attempt=attempt, pid=launch["pid"], birth=launch["birth"],
            returncode=0, actual_waitpid_observed=True))
    return root, directory, row, allowed


def runtime_gone():
    return SimpleNamespace(birth=lambda _pid: None)


def test_only_registered_old_unobserved_exit_is_exempt_and_never_fabricated(tmp_path):
    root, directory, row, allowed = setup_attempt(tmp_path)
    prepared = dict(known_unobserved_attempts=[allowed])
    controller.audit_attempt_exit(row, prepared, dict(id="science"), runtime_gone(), root)
    assert not (directory / "actual_exit/record.json").exists()
    with pytest.raises(ValueError, match="not authorized"):
        controller.audit_attempt_exit(row, dict(known_unobserved_attempts=[]),
                                      dict(id="science"), runtime_gone(), root)
    changed = copy.deepcopy(prepared)
    changed["known_unobserved_attempts"][0]["birth"] = "different-birth"
    with pytest.raises(ValueError, match="exact launch"):
        controller.audit_attempt_exit(row, changed, dict(id="science"), runtime_gone(), root)


def test_live_old_identity_and_escaped_attempt_both_block_recovery(tmp_path, monkeypatch):
    root, _, row, allowed = setup_attempt(tmp_path)
    monkeypatch.setattr(controller.inherited, "_same_live_identity", lambda *_: True)
    with pytest.raises(ValueError, match="still alive"):
        controller.audit_attempt_exit(row, dict(known_unobserved_attempts=[allowed]),
                                      dict(id="science"), runtime_gone(), root)
    with pytest.raises(ValueError, match="escaped"):
        controller.checked_attempt_directory(dict(row, directory=str(tmp_path / "attempts/attempt0001")), root)


def bare_control(root, control_root):
    value = controller.Controller.__new__(controller.Controller)
    value.root, value.control_root = root, control_root
    value.protocol, value.control_protocol = dict(id="science"), dict(id="control")
    value.controller_attempt = 1
    value.runtime = runtime_gone()
    value.accepted, value.active = {}, {}
    value.evaluation_registered, value.explicit_stop = False, False
    value.resource_wait_seconds = 12.5
    value.attempt_history = []
    value.jobs, value.job_states = {}, {}
    return value


def test_new_journal_inherits_durable_state_without_touching_old_terminal_marker(tmp_path):
    root, directory, row, allowed = setup_attempt(tmp_path)
    old_stop = root / "control/stop_requested/record.json"
    evaluation.publish(old_stop, dict(reason="actual old SIGTERM", automatic_restart_allowed=False))
    old_bytes = old_stop.read_bytes()
    control = bare_control(root, tmp_path / "control")
    key = row["job_id"]
    control.jobs = {key: dict(job_id=key, dependencies=[])}
    initial = dict(controller.inherited._initial_state(), attempts=1, progress_units=654,
                   durable_progress_digest="same-real-state")
    control.control_prepared = dict(initial_job_states={key: initial}, attempt_history=[row],
        known_unobserved_attempts=[allowed], accepted={}, evaluation_registered=False,
        resource_wait_seconds=12.5)
    control._restore_journal()
    control.journal()
    journal = evaluation.checked(control.control_root / "journal/state.json")
    assert journal["protocol_id"] == "science" and journal["control_protocol_id"] == "control"
    assert journal["job_states"][key]["attempts"] == 1
    assert journal["job_states"][key]["progress_units"] == 654
    assert journal["resource_wait_seconds"] == 12.5
    assert old_stop.read_bytes() == old_bytes
    assert not (directory / "actual_exit/record.json").exists()
    assert not (root / "journal/state.json").exists()


def test_previously_accepted_real_exit_is_inherited_without_a_new_attempt(tmp_path):
    root, directory, row, _ = setup_attempt(tmp_path, with_exit=True)
    control = bare_control(root, tmp_path / "control")
    key = row["job_id"]
    control.jobs = {key: dict(job_id=key, seed=251, stage="feedback_C05", kind="feedback", dependencies=[])}
    accepted_path = directory.parent.parent / "accepted/record.json"
    accepted = evaluation.publish(accepted_path, dict(protocol_id="science", job_id=key,
        actual_exit_zero=True, actual_exit=evaluation.file_binding(directory / "actual_exit/record.json")))
    initial = dict(controller.inherited._initial_state(), status="COMPLETE", attempts=1, accepted_attempt=1)
    control.control_prepared = dict(initial_job_states={key: initial}, attempt_history=[row],
        known_unobserved_attempts=[], accepted={key: evaluation.file_binding(accepted_path)},
        evaluation_registered=False, resource_wait_seconds=12.5)
    control._restore_journal()
    assert control.accepted[key] == accepted
    assert control.job_states[key] == initial
    assert control.ready() == []
    assert len(list(directory.parent.iterdir())) == 1


def test_new_explicit_stop_remains_terminal_and_writes_only_new_control_history(tmp_path):
    science, control_root = tmp_path / "science", tmp_path / "control"
    old_stop = science / "control/stop_requested/record.json"
    evaluation.publish(old_stop, dict(actual_original_signal=15))
    old_bytes = old_stop.read_bytes()
    control = bare_control(science, control_root)
    result = control._stop(dict(signals=[15], marker=False))
    assert result["status"] == "STOPPED_EXPLICIT_REQUEST_NO_AUTO_RESUME"
    assert controller.stop_requested(control_root)
    assert old_stop.read_bytes() == old_bytes
    assert not (science / "closeout/record.json").exists()
    with pytest.raises(ValueError, match="explicit new stop"):
        control._restore_journal()


def test_new_unsettled_journal_does_not_acquire_old_exit_exception(tmp_path):
    control = bare_control(tmp_path / "science", tmp_path / "control")
    evaluation.publish(control.control_root / "journal/state.json", dict(protocol_id="science",
        control_protocol_id="control", active_jobs=[dict(pid=9)], job_states={}))
    with pytest.raises(ValueError, match="active/unobserved"):
        control._restore_journal()


def test_signal_wrapper_preserves_science_root_attempts_and_gpu_lease(tmp_path, monkeypatch):
    control = bare_control(tmp_path / "science", tmp_path / "control")
    key = "seed251.feedback_C05"
    job = dict(job_id=key, seed=251, stage="feedback_C05", kind="feedback", dependencies=[])
    control.jobs = {key: job}
    control.job_states = {key: dict(controller.inherited._initial_state(), attempts=2)}
    control.protocol["cpu_affinity"] = {"4": "4-7"}
    control.runtime = SimpleNamespace(worker_environment=lambda _row: {}, birth=lambda _pid: "new-birth")
    control._audit = lambda _job: dict(resume_allowed=True, unknown_calls=0, progress_units=654,
                                     durable_progress_digest="same-real-state")
    lease = SimpleNamespace(fileno=lambda: 123, close=lambda: None)
    calls = []
    def popen(command, **kwargs):
        calls.append((command, kwargs))
        return SimpleNamespace(pid=999999, poll=lambda: None)
    monkeypatch.setattr(controller.subprocess, "Popen", popen)
    if hasattr(controller.os, "pidfd_open"):
        monkeypatch.setattr(controller.os, "pidfd_open", lambda *_: (_ for _ in ()).throw(ProcessLookupError()))
    control.launch(job, (dict(index=4, uuid="GPU-real"), lease, dict(original_gates=True)))
    command, kwargs = calls[0]
    assert str(control.control_root / "implementation/finqa_v57_worker.py") in command
    assert command[command.index("--mode") + 1] == "science"
    assert command[command.index("--root") + 1] == str(control.root)
    assert kwargs["pass_fds"] == (123,)
    assert kwargs["env"]["V56_ATTEMPT_ID"] == "attempt0003"
    assert kwargs["env"]["V57_SIGNAL_LOG_DIR"].endswith("attempt0003/signals")
    assert kwargs["env"]["V57_CONTROL_ROOT"] == str(control.control_root)
    assert str(controller.base.REPO / "trusted_data_synthesis/scripts") in kwargs["env"]["PYTHONPATH"].split(controller.os.pathsep)
    assert control.active[key].lease is lease
    launch = evaluation.checked(control.active[key].attempt_dir / "launch/record.json")
    assert launch["protocol_id"] == "science" and launch["control_protocol_id"] == "control"


def test_original_auxiliary_scripts_directory_remains_after_frozen_implementations(tmp_path):
    control_root, scientific_root = tmp_path / "control", tmp_path / "science"
    assert controller.execution_pythonpath(control_root, scientific_root).split(controller.os.pathsep) == [
        str(control_root / "implementation"), str(scientific_root / "implementation"),
        str(controller.base.REPO / "trusted_data_synthesis/scripts"), str(controller.evaluation.FROZEN_SOURCE)]
    assert controller.ROOT == controller.SCIENTIFIC_ROOT / "signal_recovery_02"


def test_retry_restore_retains_original_transient_audit_behavior(tmp_path):
    control = bare_control(tmp_path / "science", tmp_path / "control")
    key = "seed137.shard00"
    control.jobs = {key: dict(job_id=key, dependencies=[])}
    state = controller.inherited._initial_state()
    evaluation.publish(control.control_root / "journal/state.json", dict(protocol_id="science",
        control_protocol_id="control", active_jobs=[], job_states={key: state},
        attempt_history=[], accepted={}, evaluation_registered=False, resource_wait_seconds=14))
    control._audit = lambda _job: (_ for _ in ()).throw(OSError(errno.EIO, "temporary read error"))
    control._restore_journal()
    assert control.job_states[key]["status"] == "PRE_DISPATCH_AUDIT_WAIT"
    assert control.job_states[key]["actual_errno"] == errno.EIO


def test_killed_controller_with_unsettled_workers_is_safely_stopped_not_restarted(tmp_path, monkeypatch):
    root = tmp_path / "control"
    monkeypatch.setattr(controller, "ROOT", root)
    original = SimpleNamespace(checked_protocol=lambda _root: dict(id="science"))
    registration = SimpleNamespace(checked_protocol=lambda _root: dict(id="control", scientific_protocol_id="science"),
        checked_implementation=lambda _root: None, checked_prepared=lambda _root: dict(accepted={}))
    runtime = SimpleNamespace(birth=lambda _pid: "new-controller-birth")
    monkeypatch.setattr(controller, "initialize_science", lambda: original)
    imports = controller.importlib.import_module
    monkeypatch.setattr(controller.importlib, "import_module", lambda name: registration if name == "finqa_v57_registration"
                        else runtime if name == "finqa_v54_runtime" else imports(name))
    monkeypatch.setattr(controller.subprocess, "Popen", lambda *args, **kwargs:
                        SimpleNamespace(pid=999998, poll=lambda: -9, returncode=-9))
    monkeypatch.setattr(controller, "controller_restart_audit",
                        lambda *_: (_ for _ in ()).throw(ValueError("active/unobserved children")))
    real_stop = controller.stop_orphaned_workers
    reasons = []
    def stopped(*args, **kwargs):
        reasons.append(kwargs["reason"])
        return real_stop(*args, **kwargs)
    monkeypatch.setattr(controller, "stop_orphaned_workers", stopped)
    result = controller.supervise(root)
    assert result["status"] == "BLOCKED_CONTROLLER_EXIT_WORKER_IDENTITIES_DRAINED"
    assert result["controller_attempts"] == 1
    assert reasons[0]["kind"] == "CONTROLLER_RESTART_AUDIT_FAILED"
    assert reasons[0]["explicit_user_stop_inferred"] is False
    marker = evaluation.checked(root / "control/stop_requested/record.json")
    assert marker["schema"] == "v57_terminal_fault_stop.v1"
    assert marker["automatic_restart_allowed"] is False
    assert evaluation.checked(root / "supervisor/orphan_stop/record.json")["nonchild_waitpid_or_exit_zero_not_fabricated"]
