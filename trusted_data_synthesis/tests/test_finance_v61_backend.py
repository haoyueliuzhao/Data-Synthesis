"""CPU-only lifecycle contracts; no real launches, signals or scientific scans."""
import json
from types import SimpleNamespace

import pytest

import finqa_v61_backend as backend
import finqa_v61_observer as observer
from finqa_v61_watchdog import write_record, observation_decision


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


@pytest.fixture
def handoff_environment(environment, monkeypatch):
    env = environment
    publish_control(env)
    monkeypatch.setattr(backend, "SOURCE_CONTROL_ROOT", env.control)
    monkeypatch.setattr(backend, "SOURCE_CONTROL_PROTOCOL_ID", env.protocol["id"])
    raw = backend.observe_episode(env.master, env.episode, {})
    raw = backend.bound({**{key: item for key, item in raw.items() if key != "id"},
        "known_terminal_reason": "OWNER_TERM", "owner_term_observed": True,
        "stop_marker_present": True})
    return env, raw


def test_authorized_handoff_absent_does_not_clear_original_owner_stop(handoff_environment, monkeypatch):
    env, raw = handoff_environment
    monkeypatch.setattr(backend.importlib, "import_module", lambda name: SimpleNamespace(
        validate_authorized_stop=lambda *args: None))
    assert backend.checked_authorized_handoff(raw) is None
    assert raw["known_terminal_reason"] == "OWNER_TERM" and raw["stop_marker_present"] is True


def test_authorized_handoff_retains_original_stop_and_observation_identity(handoff_environment, monkeypatch):
    env, raw = handoff_environment
    receipt = dict(status="FINAL_AUTHORIZED_STOP", id="exact-receipt")
    seen = []
    def validate(root, episode, observed):
        seen.append((root, episode, observed))
        return receipt
    monkeypatch.setattr(backend.importlib, "import_module", lambda name: SimpleNamespace(validate_authorized_stop=validate))
    effective = backend.checked_authorized_handoff(raw)
    assert seen == [(env.master, env.episode, raw)]
    assert effective["original_observation_id"] == raw["id"]
    assert effective["original_stop_evidence"]["owner_term_observed"] is True
    assert effective["original_stop_evidence"]["known_terminal_reason"] == "OWNER_TERM"
    assert effective["authorized_handoff"] == receipt
    assert effective["known_terminal_reason"] is None and effective["stop_marker_present"] is False
    assert raw["known_terminal_reason"] == "OWNER_TERM"


@pytest.mark.parametrize("field", ["any_sigint_observed", "unfiltered_unknown_stop_signal",
    "known_hard_block", "known_implementation_failure"])
def test_handoff_never_waives_other_stop_or_failure(handoff_environment, monkeypatch, field):
    env, raw = handoff_environment
    monkeypatch.setattr(backend.importlib, "import_module", lambda name: pytest.fail("unsafe exception must not reach validator"))
    raw[field] = True
    with pytest.raises(ValueError, match="cannot be an authorized handoff"):
        backend.checked_authorized_handoff(raw)


@pytest.mark.parametrize("location", ["source", "master"])
def test_user_stop_file_cannot_be_reclassified_as_maintenance(handoff_environment, monkeypatch, location):
    env, raw = handoff_environment
    target = env.control if location == "source" else env.master
    target.mkdir(exist_ok=True)
    (target / "STOP").touch()
    monkeypatch.setattr(backend.importlib, "import_module", lambda name: pytest.fail("STOP must win"))
    with pytest.raises(ValueError, match="explicit STOP"):
        backend.checked_authorized_handoff(raw)


def test_observer_keeps_one_monitor_and_original_signal_policy_with_six_workers(monkeypatch):
    original_signals = dict(owner_SIGTERM_dispatches_original_stop=True,
        every_SIGINT_dispatches_original_stop=True)
    original_observer = dict(read_only=True, original_bounds=True)
    helper = SimpleNamespace(load_original=lambda: SimpleNamespace(observer_policy=lambda: original_observer),
        signals_policy=lambda: original_signals)
    monkeypatch.setattr(observer, "load_v59_module", lambda name: helper)
    value = observer.observer_policy()
    assert value["scientific_worker_limit"] == 6
    assert value["only_one_independent_observer"] is True and value["other_processes_signaled"] is False
    assert value["signals_policy"] == original_signals
    assert value["original_bounded_observer"] == original_observer
    assert value["resource_override"]["max_gpu_workers"] == 6
