"""CPU-only lifecycle contracts; no real launches, signals or scientific scans."""
import copy
import json
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest

import finqa_v60_backend as backend
import finqa_v60_registration as registration
from finqa_v60_watchdog import write_record, observation_decision


def record(path, **value):
    return write_record(path, value, immutable=True)


@pytest.fixture
def environment(tmp_path, monkeypatch):
    science, master, control = tmp_path / "science", tmp_path / "master", tmp_path / "control"
    monkeypatch.setattr(backend, "SCIENCE_ROOT", science)
    monkeypatch.setattr(backend, "MASTER_ROOT", master)
    protocol = dict(id="control-protocol", scientific_protocol_id=backend.SCIENTIFIC_PROTOCOL_ID)
    monkeypatch.setattr(backend, "_episode_protocol", lambda episode: protocol)
    monkeypatch.setattr(backend, "identity", lambda pid, birth: dict(pid=pid, birth=birth, alive=False))
    journal = dict(protocol_id=backend.SCIENTIFIC_PROTOCOL_ID, control_protocol_id=protocol["id"],
        active_jobs=[], job_states={}, attempt_history=[], accepted={}, evaluation_registered=False,
        resource_wait_seconds=123.0)
    episode = dict(root=str(control), protocol_id=protocol["id"])
    return SimpleNamespace(science=science, master=master, control=control,
                           protocol=protocol, journal=journal, episode=episode)


def publish_control(env):
    record(env.control / "journal/state.json", **env.journal)
    record(env.control / "supervisor/launch/record.json", control_protocol_id=env.protocol["id"], pid=101, birth="12")


def test_healthy_observation_never_imports_science_or_reads_task_attempts(environment, monkeypatch):
    env = environment
    publish_control(env)
    monkeypatch.setattr(backend, "identity", lambda pid, birth: dict(pid=pid, birth=birth, alive=True))
    monkeypatch.setattr(backend, "_load_science", lambda: pytest.fail("healthy original science import"))
    monkeypatch.setattr(backend, "_attempt_path", lambda row: pytest.fail("healthy task audit"))
    result = backend.observe_episode(env.master, env.episode, {})
    assert observation_decision(result, env.episode)["status"] == "WATCHING_LIVE_EPISODE"
    assert not result["actual_waitpid_observed"] and result["actual_returncode"] is None


def test_all_gone_without_waitpid_remains_unknown(environment):
    env = environment
    publish_control(env)
    result = backend.observe_episode(env.master, env.episode, {})
    assert observation_decision(result, env.episode)["category"] == "ALL_IDENTITIES_GONE_EXIT_UNKNOWN"
    assert result["actual_returncode"] is None


def test_dispatch_intent_without_child_or_nochild_proof_blocks(environment):
    env = environment
    directory = env.science / "stages/seed137/shard01/attempts/attempt0001"
    row = dict(job_id="seed137.shard01", attempt=1, directory=str(directory))
    env.journal["attempt_history"] = [row]
    env.journal["job_states"][row["job_id"]] = dict(status="DISPATCHING")
    record(directory / "dispatch_intent/record.json", control_protocol_id=env.protocol["id"])
    publish_control(env)
    result = backend.observe_episode(env.master, env.episode, {})
    assert not result["identity_roster_complete"]
    assert observation_decision(result, env.episode)["action"] == "WAIT"


def test_supervisor_popen_hole_without_any_controller_receipt_blocks(environment):
    env = environment
    publish_control(env)
    (env.control / "supervisor/attempts/attempt0001").mkdir(parents=True)
    result = backend.observe_episode(env.master, env.episode, {})
    assert not result["identity_roster_complete"]
    assert observation_decision(result, env.episode)["action"] == "WAIT"


def test_parent_observed_observer_launch_waits_for_early_receipt_without_assuming_missing(environment):
    env = environment
    directory = env.control / "runner/children/observer"
    record(directory / "intent/record.json", control_protocol_id=env.protocol["id"], dispatch_token_sha256="token")
    record(directory / "launch/record.json", control_protocol_id=env.protocol["id"],
        role="observer", actual_child_created=True, pid=123, birth="456")
    assert backend._observer_launch(env.control)["birth"] == "456"


def test_runner_real_waitpid_negative_nine_is_not_inferred(environment):
    env = environment
    publish_control(env)
    record(env.control / "runner/supervisor_actual_exit/record.json", control_protocol_id=env.protocol["id"],
           actual_waitpid_observed=True, returncode=-9, pid=101, birth="12")
    result = backend.observe_episode(env.master, env.episode, {})
    assert observation_decision(result, env.episode)["category"] == "CONFIRMED_SIGKILL"


def test_only_current_episode_foreign_kernel_term_is_filtered(environment, monkeypatch):
    env = environment
    def decision(number, sender, uid, code):
        return dict(filtered=number == 15 and uid == 0 and code == 0 and sender > 0)
    monkeypatch.setattr(backend, "load_v59_module", lambda name: SimpleNamespace(signal_decision=decision))
    current = env.control / "signals/supervisor-101/received.jsonl"
    current.parent.mkdir(parents=True)
    event = dict(schema="v59_received_signal_kernel_receipt.v1", signal=15, si_pid=901, si_uid=0,
                 si_code=0, provenance="kernel_sigwaitinfo", decision=decision(15, 901, 0, 0))
    current.write_text(json.dumps(event) + "\n")
    old = env.science / "old-control/signals/received.jsonl"
    old.parent.mkdir(parents=True)
    old.write_text(json.dumps(dict(event, si_uid=1004, decision=decision(15, 901, 1004, 0))) + "\n")
    result = backend._stop_evidence(env.control, env.journal, [])
    assert result["known_terminal_reason"] is None
    current.write_text(json.dumps(dict(event, si_uid=1004, decision=decision(15, 901, 1004, 0))) + "\n")
    assert backend._stop_evidence(env.control, env.journal, [])["known_terminal_reason"] == "OWNER_TERM"


def test_observer_signal_is_monitor_lifecycle_not_scientific_stop(environment):
    env = environment
    path = env.control / "signals/observer-909/received.jsonl"
    path.parent.mkdir(parents=True)
    path.write_text(json.dumps(dict(schema="v59_received_signal_kernel_receipt.v1", role="observer",
        signal=2, si_uid=1004)) + "\n")
    assert backend._stop_evidence(env.control, env.journal, [])["known_terminal_reason"] is None


def test_controller_failure_before_stop_or_journal_commit_is_not_hidden(environment):
    env = environment
    record(env.control / "controllers/attempt0001/failure/record.json",
        control_protocol_id=env.protocol["id"], error_type="ModuleNotFoundError",
        transient_without_active_children=False, active_children=[], actual_errno=None)
    result = backend._stop_evidence(env.control, env.journal, [])
    assert result["known_terminal_reason"] == "IMPLEMENTATION_FAILURE"


def test_recorded_historical_hard_resource_peak_blocks_unknown_exit_recovery(environment):
    env = environment
    directory = env.science / "stages/seed137/shard01/attempts/attempt0001"
    row = dict(job_id="seed137.shard01", attempt=1, directory=str(directory))
    env.journal["job_states"][row["job_id"]] = dict(status="RUNNING")
    record(directory / "launch/record.json", pid=501, birth="61", job=dict(kind="class"))
    record(env.science / "resources/seed137.shard01/pid501/closeout/record.json",
        pid=501, job_id=row["job_id"], resources=dict(peak_allocated_bytes=77 * 1024 ** 3, peak_rss_bytes=100))
    assert backend._stop_evidence(env.control, env.journal, [row])["known_terminal_reason"] == "HARD_BLOCKED"


def test_observer_must_be_alive_with_fresh_readable_heartbeat_before_scientific_spawn(environment, monkeypatch):
    env = environment
    monkeypatch.setattr(backend, "identity", lambda pid, birth: dict(pid=pid, birth=birth, alive=True))
    monkeypatch.setattr(backend, "_observer_launch", lambda control: dict(pid=201, birth="44"))
    process = SimpleNamespace(pid=201, poll=lambda: None)
    heartbeat = dict(schema="v58_independent_observer_heartbeat.v1", pid=201, birth="44",
        root=str(env.control), status="RUNNING", current_discovery_readable=True, at_epoch=backend.time.time())
    path = env.control / "observer/queue/status.json"
    path.parent.mkdir(parents=True)
    path.write_text(json.dumps(heartbeat))
    assert backend._wait_observer_ready(env.control, process, "44", []) is True
    dead = SimpleNamespace(pid=201, poll=lambda: 1)
    with pytest.raises(ValueError, match="observer exited"):
        backend._wait_observer_ready(env.control, dead, "44", [])


def test_retirement_never_signals_when_any_scientific_identity_alive(environment, monkeypatch):
    env = environment
    monkeypatch.setattr(backend.os, "kill", lambda *args: pytest.fail("scientific live roster must prevent TERM"))
    with pytest.raises(ValueError, match="fully stopped"):
        backend.retire_observer(env.master, env.episode,
            dict(identity_roster_complete=True, identities=[dict(pid=1, birth="3", alive=True)]), "request000001")


def test_observer_retirement_uses_pidfd_once_and_separates_intent_from_delivery(environment, monkeypatch):
    env = environment
    env.protocol["observer_policy"] = {}
    monkeypatch.setattr(backend, "_observer_launch", lambda control: dict(pid=201, birth="44"))
    monkeypatch.setattr(backend, "identity", lambda pid, birth: dict(pid=pid, birth=birth, alive=pid == 201))
    monkeypatch.setattr(backend, "_owner_uids", lambda pid: (1004, 1004, 1004, 1004))
    monkeypatch.setattr(backend.importlib, "import_module", lambda name: SimpleNamespace(observer_policy=lambda: {}))
    monkeypatch.setattr(backend, "_pidfd_open", lambda pid: 9876)
    sent, closed = [], []
    monkeypatch.setattr(backend, "_pidfd_term", lambda descriptor: sent.append((descriptor, 15)))
    real_close = backend.os.close
    monkeypatch.setattr(backend.os, "close", lambda descriptor: closed.append(descriptor) if descriptor == 9876 else real_close(descriptor))
    observation = dict(identity_roster_complete=True, identities=[dict(pid=101, birth="12", alive=False)])
    one = backend.retire_observer(env.master, env.episode, observation, "request000001")
    two = backend.retire_observer(env.master, env.episode, observation, "request000001")
    assert one["status"] == two["status"] == "WAITING_FOR_OBSERVER_EXIT"
    assert sent == [(9876, 15)] and closed == [9876]
    intent = backend.checked_record(env.control / "observer/retirement_intent/record.json")
    delivery = backend.checked_record(env.control / "observer/retirement_dispatch/record.json")
    assert intent["signal_delivery_observed"] is False and delivery["pidfd_send_returned_successfully"] is True


def test_token_bound_early_runner_receipt_reconciles_without_second_popen(environment, monkeypatch):
    env = environment
    receipt = dict(episode_root=str(env.control), control_protocol_id=env.protocol["id"])
    directory = backend._dispatch_directory(env.master, "request000001", 1)
    record(directory / "intent/record.json", dispatch_token_sha256="tokenhash")
    record(env.control / "runner/launch/record.json", dispatch_token_sha256="tokenhash",
        dispatch_directory=str(directory), control_protocol_id=env.protocol["id"], pid=234, birth="567")
    monkeypatch.setattr(backend.subprocess, "Popen", lambda *a, **k: pytest.fail("reconciliation cannot create child"))
    result = backend.reconcile_launch(env.master, receipt, "request000001", 1)
    assert result["status"] == "LAUNCHED" and result["pid"] == 234 and result["birth"] == "567"


def test_unobserved_runner_dispatch_never_means_safe_nochild(environment):
    env = environment
    receipt = dict(episode_root=str(env.control), control_protocol_id=env.protocol["id"])
    directory = backend._dispatch_directory(env.master, "request000001", 1)
    record(directory / "intent/record.json", dispatch_token_sha256="tokenhash")
    result = backend.reconcile_launch(env.master, receipt, "request000001", 1)
    assert result["status"] == "UNKNOWN_CHILD_CREATION" and result["actual_child_created"] is None


def test_successor_registration_resumes_identical_partial_transaction(tmp_path, monkeypatch):
    master = tmp_path / "master"
    science = tmp_path / "science"
    destination = master / "episodes/episode000001"
    monkeypatch.setattr(registration, "MASTER_ROOT", master)
    monkeypatch.setattr(registration, "SCIENCE_ROOT", science)
    monkeypatch.setattr(registration, "episode_root", lambda path: Path(path))
    master_protocol = dict(id="master", implementation=dict(path="immutable", id="manifest", sha256="hash"),
        scientific_protocol=dict(path="science", id="science", sha256="hash"), signals_policy={}, gpu_isolation_policy={})
    monkeypatch.setattr(registration, "checked_master_protocol", lambda root=None: master_protocol)
    monkeypatch.setattr(registration, "policy_modules", lambda: (None,
        SimpleNamespace(adapter_contract=lambda path: dict(root=str(path))),
        SimpleNamespace(observer_policy=lambda: dict(readonly=True))))
    observed = record(master / "requests/request000001/exit_observation/record.json", identity_roster_complete=True)
    bootstrap = {key: {} for key in registration.BOOTSTRAP_FIELDS}
    bootstrap.update(attempt_history=[dict(job_id="j", attempt=7)], resource_wait_seconds=123,
                     known_unobserved_attempts=[dict(old_returncode=None)], evaluation_registered=False)
    audit = record(master / "requests/request000001/durable_audit/record.json", observation_id=observed["id"],
        stop_audit_complete=True, same_scientific_state=True, accepted_records_valid=True,
        historical_budgets_and_attempts_preserved=True, original_job_audits_used=True,
        owner_term_observed=False, any_sigint_observed=False, stop_marker_present=False,
        known_hard_block=False, known_implementation_failure=False, jobs={}, required_jobs=[],
        progress_before={}, bootstrap=bootstrap)
    real_publish = registration.publish
    def interrupted(path, value):
        if Path(path) == destination / "prepared/record.json":
            raise OSError("synthetic interruption after immutable protocol")
        return real_publish(path, value)
    monkeypatch.setattr(registration, "publish", interrupted)
    predecessor = dict(root="old", protocol_id="old-protocol")
    with pytest.raises(OSError):
        registration.register_successor(master, predecessor, observed, audit, "request000001")
    original_protocol = (destination / "protocol/record.json").read_bytes()
    monkeypatch.setattr(registration, "publish", real_publish)
    one = registration.register_successor(master, predecessor, observed, audit, "request000001")
    two = registration.register_successor(master, predecessor, observed, audit, "request000001")
    assert one == two and original_protocol == (destination / "protocol/record.json").read_bytes()
    prepared = backend.checked_record(destination / "prepared/record.json")
    assert prepared["resource_wait_seconds"] == 123 and prepared["attempt_history"][0]["attempt"] == 7
    assert prepared["known_unobserved_attempts"][0]["old_returncode"] is None
    assert prepared["new_feedback_budget"] == 0 and not one["budgets_reset"]


def test_interrupted_durable_audit_reuses_completed_job_cache_and_sha_only_accepted(environment, monkeypatch):
    env = environment
    pending = dict(job_id="seed137.train_Hold", seed=137, stage="train_Hold", kind="train")
    accepted_job = "seed251.feedback_C05"
    env.journal["job_states"] = {
        pending["job_id"]: dict(status="PENDING", attempts=0, no_progress_failures=3,
            next_eligible_epoch=999.0, progress_units=0, durable_progress_digest="old"),
        accepted_job: dict(status="COMPLETE", attempts=0, no_progress_failures=0,
            next_eligible_epoch=0.0, progress_units=700, durable_progress_digest="accepted")}
    result_path, exit_path, accepted_path = [env.science / name / "record.json"
                                            for name in ("result", "actual_exit", "accepted")]
    record(result_path, status="COMPLETE", resources=dict(all_gates_passed=True))
    record(exit_path, actual_waitpid_observed=True, returncode=0)
    def legacy_ref(path):
        return dict(path=str(path), sha256=registration.sha(path))
    record(accepted_path, actual_exit_zero=True, actual_exit=legacy_ref(exit_path), result=legacy_ref(result_path))
    env.journal["accepted"] = {accepted_job: legacy_ref(accepted_path)}
    publish_control(env)
    record(env.control / "prepared/record.json", resume_audits={})
    for seed in (137, 251, 389):
        record(env.science / f"parents/seed{seed}/record.json", seed=seed)
    calls = []
    audit = dict(resume_allowed=True, unknown_calls=0, progress_units=12,
                 durable_progress_digest="actual-twelve", evidence=[])
    worker = SimpleNamespace(__file__="original-frozen-worker", audit_job_resume=lambda root, job: calls.append(job) or audit)
    controller = SimpleNamespace(core_jobs=lambda parents: {pending["job_id"]: pending,
        accepted_job: dict(job_id=accepted_job, seed=251, stage="feedback_C05", kind="feedback")})
    monkeypatch.setattr(backend, "_load_science", lambda: (worker, controller, SimpleNamespace()))
    monkeypatch.setitem(sys.modules, "torch", SimpleNamespace(cuda=SimpleNamespace(is_initialized=lambda: False)))
    observed = backend.bound(backend.observe_episode(env.master, env.episode, {}))
    real_write = backend.write_record
    def interrupted(path, value, **kwargs):
        if Path(path).parent.name == "identities":
            raise OSError("synthetic interruption after one successful original job audit")
        return real_write(path, value, **kwargs)
    monkeypatch.setattr(backend, "write_record", interrupted)
    with pytest.raises(OSError):
        backend.audit_durable(env.master, env.episode, observed)
    assert len(calls) == 1
    monkeypatch.setattr(backend, "write_record", real_write)
    result = backend.audit_durable(env.master, env.episode, observed)
    assert len(calls) == 1 and result["jobs"][pending["job_id"]]["progress_units"] == 12
    assert result["bootstrap"]["initial_job_states"][pending["job_id"]]["no_progress_failures"] == 3
    assert result["bootstrap"]["initial_job_states"][pending["job_id"]]["next_eligible_epoch"] == 999.0
    assert result["bootstrap"]["resource_wait_seconds"] == 123.0
    assert result["bootstrap"]["accepted"] == env.journal["accepted"]
