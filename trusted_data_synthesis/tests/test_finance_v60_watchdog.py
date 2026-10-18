import copy
import errno
import fcntl
from pathlib import Path

import pytest

import finqa_v60_watchdog as watchdog


class Backend:
    def __init__(self, root, science, initial):
        self.root, self.science, self.initial = root, science, initial
        self.calls = []
        self.observation_changes, self.audit_changes = {}, {}
        self.launch_error, self.reconciled_launch = None, None
        self.retirement_wait = False
        self.budget_reset = False
        paths = [science / "owner.lock"] + [watchdog.GPU_LEASE_ROOT /
            ("gpu-" + watchdog.digest(f"GPU-{index}") + ".lock") for index in range(8)]
        self.original_lock_bindings = {str(path): dict(device=path.stat().st_dev, inode=path.stat().st_ino)
                                       for path in paths}

    def checked_protocol(self, root):
        return dict(id="guard-protocol", root=str(root), scientific_root=str(self.science),
            policy=watchdog.policy(), gpu_lease_root=str(watchdog.GPU_LEASE_ROOT),
            gpu_uuids={str(index): f"GPU-{index}" for index in range(8)},
            original_lock_bindings=self.original_lock_bindings)

    def checked_prepared(self, root):
        return dict(protocol_id="guard-protocol", initial_episode=dict(root=str(self.initial), protocol_id="initial-protocol"))

    def observe_episode(self, root, episode, state):
        self.calls.append("observe")
        value = dict(episode_root=episode["root"], control_protocol_id=episode["protocol_id"],
            identity_roster_complete=True, identities=[
                dict(role="supervisor", pid=101, birth="birth101", alive=False),
                dict(role="scientific_worker", pid=102, birth="birth102", alive=False)],
            known_terminal_reason=None, stop_marker_present=False, experiment_complete=False,
            actual_waitpid_observed=False, actual_returncode=None)
        value.update(self.observation_changes)
        return value

    def audit_durable(self, root, episode, observation):
        self.calls.append("audit")
        value = dict(observation_id=observation["id"], stop_audit_complete=True,
            same_scientific_state=True, accepted_records_valid=True,
            historical_budgets_and_attempts_preserved=True, original_job_audits_used=True,
            owner_term_observed=False, any_sigint_observed=False, stop_marker_present=False,
            known_hard_block=False, known_implementation_failure=False,
            required_jobs=["seed137.shard01"], progress_before={"seed137.shard01": 10},
            jobs={"seed137.shard01": dict(resume_allowed=True, unknown_calls=0, progress_units=12,
                                         durable_progress_digest="actual-complete-task-digest")})
        value.update(copy.deepcopy(self.audit_changes))
        return value

    def retire_observer(self, root, episode, observation, request_id):
        self.calls.append("retire")
        value = dict(status="NO_LIVE_OBSERVER", scientific_processes_signaled=False,
            unowned_processes_signaled=False, observer_roster_verified=True,
            remaining_independent_observers=0, all_observer_identities_gone=True)
        if self.retirement_wait:
            value.update(status="WAITING_FOR_OBSERVER_EXIT", remaining_independent_observers=1,
                         all_observer_identities_gone=False)
        return value

    def register_episode(self, root, predecessor, observation, audits, request_id):
        self.calls.append("register")
        number = int(request_id.removeprefix("request"))
        return dict(episode_root=str(root / "episodes" / f"episode{number:06d}"),
            scientific_root=str(self.science), request_id=request_id, predecessor_root=predecessor["root"],
            ready_for_launch=True, budgets_reset=self.budget_reset, attempts_reset=False,
            control_protocol_id=f"successor-{number}", registration_id=f"registration-{number}")

    def launch_registered(self, root, receipt, request_id, launch_attempt):
        self.calls.append("launch")
        result = dict(status="LAUNCHED", actual_child_created=True, episode_root=receipt["episode_root"],
            request_id=request_id, control_protocol_id=receipt["control_protocol_id"],
            pid=201, birth="actual-successor-birth")
        if self.launch_error is not None:
            self.reconciled_launch = result
            raise self.launch_error
        return result

    def reconcile_launch(self, root, receipt, request_id, launch_attempt):
        self.calls.append("reconcile")
        return self.reconciled_launch or dict(status="UNKNOWN", actual_child_created=None)


@pytest.fixture
def context(tmp_path, monkeypatch):
    science, root, initial, leases = (tmp_path / name for name in ("science", "guard", "initial", "leases"))
    for path in (science, root, initial, leases):
        path.mkdir()
    monkeypatch.setattr(watchdog, "ROOT", root)
    monkeypatch.setattr(watchdog, "SCIENCE_ROOT", science)
    monkeypatch.setattr(watchdog, "INITIAL_EPISODE_ROOT", initial)
    monkeypatch.setattr(watchdog, "GPU_LEASE_ROOT", leases)
    (science / "owner.lock").touch()
    for index in range(8):
        (leases / ("gpu-" + watchdog.digest(f"GPU-{index}") + ".lock")).touch()
    return root, Backend(root, science, initial)


def available(_protocol):
    return dict(available=True, leases_retained=0, all_acquired_released=True)


def test_live_scientific_worker_prevents_audit_retirement_and_second_pool(context):
    root, backend = context
    backend.observation_changes = dict(identities=[dict(role="scientific_worker", pid=102, birth="birth102", alive=True)])
    result = watchdog.tick(root, backend=backend, lease_probe=lambda _: pytest.fail("live pool must not probe leases"))
    assert result["status"] == "WATCHING_LIVE_EPISODE"
    assert backend.calls == ["observe"]
    assert not (root / "requests").exists()


def test_missing_birth_cannot_be_treated_as_all_identities_confirmed_gone(context):
    root, backend = context
    backend.observation_changes = dict(identities=[dict(role="scientific_worker", pid=102, birth=None, alive=False)])
    result = watchdog.tick(root, backend=backend, lease_probe=lambda _: pytest.fail("identity evidence incomplete"))
    assert result["status"] == "WAITING_FOR_COMPLETE_EXIT_OBSERVATION"
    assert backend.calls == ["observe"]


@pytest.mark.parametrize("reason", ["OWNER_TERM", "SIGINT", "UNKNOWN_FEEDBACK", "NUMERICAL_FAILURE", "IMPLEMENTATION_FAILURE"])
def test_known_terminal_reason_is_persistent_and_never_launches(context, reason):
    root, backend = context
    original = backend.observe_episode
    backend.observe_episode = lambda *args: {**original(*args), "known_terminal_reason": reason}
    first = watchdog.tick(root, backend=backend, lease_probe=available)
    backend.observe_episode = original
    second = watchdog.tick(root, backend=backend, lease_probe=available)
    assert first["status"] == second["status"] == "STOPPED_NO_AUTO_RECOVERY"
    assert backend.calls == ["observe"]
    assert watchdog.checked(root / "terminal/record.json")["automatic_recovery_allowed"] is False


@pytest.mark.parametrize("observed,code,category", [(False, None, "ALL_IDENTITIES_GONE_EXIT_UNKNOWN"), (True, -9, "CONFIRMED_SIGKILL")])
def test_authorized_disappearance_creates_fresh_episode_without_fabricating_exit(context, observed, code, category):
    root, backend = context
    original = backend.observe_episode
    backend.observe_episode = lambda *args: {**original(*args), "actual_waitpid_observed": observed,
                                           "actual_returncode": code}
    result = watchdog.tick(root, backend=backend, lease_probe=available)
    assert result["status"] == "SUCCESSOR_LAUNCH_OBSERVED"
    assert backend.calls == ["observe", "audit", "observe", "retire", "register", "observe", "launch"]
    state = watchdog.checked(root / "state.json")
    assert state["current_episode"]["root"] == str(root / "episodes/episode000001")
    intent = watchdog.checked(root / "requests/request000001/intent/record.json")
    assert intent["recovery_category"] == category
    old = watchdog.checked(root / "requests/request000001/exit_observation/record.json")
    assert old["actual_returncode"] is code or old["actual_returncode"] == code
    assert not (backend.initial / "startup_verification").exists()


def test_unknown_feedback_in_original_audit_is_a_permanent_stop(context):
    root, backend = context
    backend.audit_changes = dict(jobs={"seed137.shard01": dict(resume_allowed=False, unknown_calls=1,
        progress_units=12, durable_progress_digest="unknown-call")})
    result = watchdog.tick(root, backend=backend, lease_probe=available)
    assert result["status"] == "BLOCKED_DURABLE_OR_IMPLEMENTATION_AUDIT"
    assert backend.calls == ["observe", "audit"]
    retained = watchdog.checked(root / "requests/request000001/durable_audit/record.json")
    assert retained["jobs"]["seed137.shard01"]["unknown_calls"] == 1


def test_owner_stop_found_by_complete_receipt_audit_blocks_monitor_retirement(context):
    root, backend = context
    backend.audit_changes = dict(owner_term_observed=True)
    result = watchdog.tick(root, backend=backend, lease_probe=available)
    assert result["automatic_recovery_terminal"] is True
    assert "retire" not in backend.calls and "launch" not in backend.calls


def test_observer_exit_wait_does_not_repeat_durable_audit_or_start_new_observer(context):
    root, backend = context
    backend.retirement_wait = True
    assert watchdog.tick(root, backend=backend, lease_probe=available)["status"] == "WAITING_FOR_OWN_READONLY_OBSERVER_EXIT"
    assert "launch" not in backend.calls and "register" not in backend.calls
    backend.retirement_wait = False
    assert watchdog.tick(root, backend=backend, lease_probe=available)["status"] == "SUCCESSOR_LAUNCH_OBSERVED"
    assert backend.calls.count("audit") == 1
    assert backend.calls.count("retire") == 2 and backend.calls.count("launch") == 1


def test_scientific_identity_appearing_during_audit_prevents_monitor_retirement(context):
    root, backend = context
    original = backend.audit_durable
    def audit(*args):
        result = original(*args)
        backend.observation_changes = dict(identities=[dict(
            role="scientific_worker", pid=102, birth="birth102", alive=True)])
        return result
    backend.audit_durable = audit
    result = watchdog.tick(root, backend=backend, lease_probe=available)
    assert result["status"] == "WATCHING_LIVE_EPISODE"
    assert "retire" not in backend.calls and "launch" not in backend.calls


def test_budget_reset_from_registration_is_rejected_before_launch(context):
    root, backend = context
    backend.budget_reset = True
    result = watchdog.tick(root, backend=backend, lease_probe=available)
    assert result["automatic_recovery_terminal"] is True
    assert "launch" not in backend.calls


def test_busy_project_lease_prevents_audit_and_releases_earlier_locks(context):
    root, backend = context
    protocol = backend.checked_protocol(root)
    busy = watchdog.GPU_LEASE_ROOT / ("gpu-" + watchdog.digest(protocol["gpu_uuids"]["3"]) + ".lock")
    with busy.open("a") as occupied:
        fcntl.flock(occupied, fcntl.LOCK_EX | fcntl.LOCK_NB)
        result = watchdog.tick(root, backend=backend)
        assert result["status"] == "WAITING_FOR_ORIGINAL_PROJECT_LEASES"
        assert backend.calls == ["observe"]
        earlier = watchdog.GPU_LEASE_ROOT / ("gpu-" + watchdog.digest(protocol["gpu_uuids"]["0"]) + ".lock")
        with earlier.open("a") as released:
            fcntl.flock(released, fcntl.LOCK_EX | fcntl.LOCK_NB)


def test_missing_original_lease_is_not_created_and_previously_acquired_locks_are_released(context):
    root, backend = context
    protocol = backend.checked_protocol(root)
    missing = watchdog.GPU_LEASE_ROOT / ("gpu-" + watchdog.digest(protocol["gpu_uuids"]["1"]) + ".lock")
    missing.unlink()
    result = watchdog.tick(root, backend=backend)
    assert result["status"] == "BLOCKED_GUARD_IO_OR_STATE"
    assert not missing.exists()
    assert backend.calls == ["observe"]
    earlier_gpu = watchdog.GPU_LEASE_ROOT / ("gpu-" + watchdog.digest(protocol["gpu_uuids"]["0"]) + ".lock")
    for path in (watchdog.SCIENCE_ROOT / "owner.lock", earlier_gpu):
        with path.open("r+") as released:
            fcntl.flock(released, fcntl.LOCK_EX | fcntl.LOCK_NB)


def test_interrupted_launch_reconciles_real_child_before_lease_probe_and_never_relaunches(context):
    root, backend = context
    backend.launch_error = OSError(errno.EIO, "interrupted after actual child creation")
    first = watchdog.tick(root, backend=backend, lease_probe=available)
    assert first["status"] == "WAITING_FOR_LAUNCH_RECONCILIATION"
    second = watchdog.tick(root, backend=backend, lease_probe=lambda _: pytest.fail("new child may already own leases"))
    assert second["status"] == "SUCCESSOR_LAUNCH_OBSERVED"
    assert backend.calls.count("launch") == 1 and backend.calls.count("reconcile") == 1


def test_existing_launch_receipt_is_reconciled_before_old_journal_new_dispatch_wait(context):
    root, backend = context
    backend.launch_error = OSError(errno.EIO, "tick disappeared after the successor was created")
    first = watchdog.tick(root, backend=backend, lease_probe=available)
    assert first["status"] == "WAITING_FOR_LAUNCH_RECONCILIATION"
    backend.observation_changes = dict(identity_roster_complete=False,
        unresolved_dispatches=[str(backend.science / "stages/seed137/shard01/attempts/attempt0006")])
    second = watchdog.tick(root, backend=backend, lease_probe=lambda _: pytest.fail("reconciliation is read-only"))
    assert second["status"] == "SUCCESSOR_LAUNCH_OBSERVED"
    assert watchdog.checked(root / "state.json")["current_episode"]["root"] == str(root / "episodes/episode000001")
    assert backend.calls.count("launch") == backend.calls.count("reconcile") == 1
    assert backend.calls.count("audit") == backend.calls.count("register") == 1


def test_ambiguous_child_creation_is_permanently_blocked(context):
    root, backend = context
    backend.launch_error = RuntimeError("no reliable launch receipt")
    watchdog.tick(root, backend=backend, lease_probe=available)
    backend.reconciled_launch = None
    result = watchdog.tick(root, backend=backend, lease_probe=available)
    assert result["status"] == "BLOCKED_AMBIGUOUS_LAUNCH"
    assert backend.calls.count("launch") == 1


def test_tick_lock_and_dedicated_stop_do_not_call_backend_observation(context):
    root, backend = context
    with (root / "tick.lock").open("a") as owned:
        fcntl.flock(owned, fcntl.LOCK_EX | fcntl.LOCK_NB)
        assert watchdog.tick(root, backend=backend)["status"] == "SKIP_TICK_ALREADY_RUNNING"
    (root / "STOP").touch()
    assert watchdog.tick(root, backend=backend, lease_probe=available)["status"] == "STOPPED_NO_AUTO_RECOVERY"
    assert backend.calls == []


def test_preflight_binding_failure_is_fenced_even_if_backend_is_later_repaired(context):
    root, backend = context
    original = backend.checked_protocol
    backend.checked_protocol = lambda _root: (_ for _ in ()).throw(ValueError("changed frozen registration"))
    assert watchdog.tick(root, backend=backend, lease_probe=available)["status"] == "BLOCKED_PREFLIGHT_CONTRACT"
    backend.checked_protocol = original
    assert watchdog.tick(root, backend=backend, lease_probe=available)["status"] == "BLOCKED_PREFLIGHT_CONTRACT"
    assert backend.calls == []
