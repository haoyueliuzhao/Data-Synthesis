"""CPU/mock tests for the independent V63 queue; no process/GPU dispatch."""
from __future__ import annotations

import errno
from types import SimpleNamespace

import pytest

import finqa_v63_binding as binding
import finqa_v63_controller as controller
import finqa_v63_evaluation as evaluation
import finqa_v63_queue_base as base


@pytest.fixture
def root(tmp_path, monkeypatch):
    monkeypatch.setattr(binding, "ROOT", tmp_path)
    monkeypatch.setattr(controller, "ROOT", tmp_path)
    return tmp_path


def parents():
    return {str(seed): dict(seed=seed, id=f"parent-{seed}") for seed in binding.SEEDS}


def evidence(root):
    path = root / "evidence/record.json"
    evaluation.publish(path, dict(actual_resource_error=True))
    return evaluation.file_binding(path)


def audit(reference, progress=10, unknown=0):
    return dict(resume_allowed=True, unknown_calls=unknown, progress_units=progress,
                durable_progress_digest="actual-bound-checkpoint", evidence=[reference])


def test_exact_six_new_condition_chains_no_class_or_hold():
    jobs = base.core_jobs(parents())
    assert len(jobs) == 24
    assert {job["kind"] for job in jobs.values()} == {"feedback", "replay", "distribution", "train"}
    assert len([job for job in jobs.values() if job["kind"] == "train"]) == 6
    for seed in binding.SEEDS:
        for arm in binding.ARMS:
            previous = None
            for phase in ("feedback", "replay", "distribution", "train"):
                key = f"seed{seed}.{phase}_{arm}"
                job = jobs[key]
                assert job["dependencies"] == ([] if previous is None else [previous])
                assert job["feedback_batch"] == 1 and job["arm"] == arm
                assert job["temperature"] == binding.TEMPERATURES[arm]
                previous = key


def test_saved_complete_never_hides_nonzero_controller_exit():
    assert controller.controller_closeout_status(dict(status="COMPLETE"), 0) == "COMPLETE"
    assert controller.controller_closeout_status(dict(status="COMPLETE"), -9) == "CONTROLLER_NONZERO_AFTER_CLOSEOUT"
    assert controller.controller_closeout_status(dict(status="BLOCKED_OPERATOR_REQUIRED"), 2) == "BLOCKED_OPERATOR_REQUIRED"


def test_six_slots_count_initializing_waiting_and_draining_and_one_per_gpu():
    active = {str(i): SimpleNamespace(gpu=i, lifecycle="DRAINING" if i == 0 else "RUNNING")
              for i in range(6)}
    assert base.MAX_WORKERS == 6 and base.can_dispatch(active) is False
    assert base.can_dispatch({key: value for key, value in active.items() if key != "5"}) is True
    with pytest.raises(ValueError, match="six-worker"):
        base.can_dispatch({**active, "extra": SimpleNamespace(gpu=6)})
    active["5"].gpu = 0
    with pytest.raises(ValueError, match="one experiment worker"):
        base.can_dispatch(active)
    assert base.process_state(SimpleNamespace(poll=lambda: None), True) == ("DRAINING", None)
    assert base.process_state(SimpleNamespace(poll=lambda: 0), True) == ("EXITED_SUCCESS", 0)


def test_shared_gpu_requires_known_owner_and_exact_uuid_and_memory():
    protocol = dict(gpu_uuids={"0": "GPU-original"})
    row = dict(index=0, uuid="GPU-original", free_mib=100 * 1024,
               gpu_isolation=dict(allowed=True, gpu_uuid="GPU-original"))
    assert base.gpu_eligible(row, protocol, dict(kind="train"))
    assert not base.gpu_eligible(dict(row, gpu_isolation={}), protocol, dict(kind="train"))
    assert not base.gpu_eligible(dict(row, free_mib=1), protocol, dict(kind="train"))
    with pytest.raises(ValueError, match="UUID"):
        base.gpu_eligible(dict(row, uuid="GPU-reused"), protocol, dict(kind="train"))


def test_owner_gate_is_rechecked_after_acquiring_original_lease(root, monkeypatch):
    monkeypatch.setattr(base, "GPU_LEASE_ROOT", root / "leases")
    queue = base.Controller.__new__(base.Controller)
    queue.active, queue.priority, queue.protocol = {}, [0], dict(gpu_uuids={"0": "GPU-original"})
    admitted = dict(index=0, uuid="GPU-original", free_mib=100 * 1024,
                    gpu_isolation=dict(allowed=True, gpu_uuid="GPU-original"))
    observations = iter(([admitted], []))
    queue.runtime = SimpleNamespace(inventory=lambda: next(observations))
    queue._host_gate = lambda job: dict(available_bytes=1, required_bytes=1)
    assert queue.acquire(dict(kind="train")) is None
    # The lock is released, never retained to force other work to drain.
    with (root / "leases" / ("gpu-" + binding.digest("GPU-original") + ".lock")).open("a") as stream:
        controller.fcntl.flock(stream, controller.fcntl.LOCK_EX | controller.fcntl.LOCK_NB)


def test_resource_backoff_and_long_cooldown_require_actual_evidence(root):
    ref = evidence(root)
    failure = dict(classification="RETRY_SAFE_RESOURCE", evidence=[ref])
    value = controller.failure_decision(failure, audit(ref), previous_units=10,
                                        no_progress_failures=3, attempt=4)
    assert value["status"] == "RESOURCE_COOLDOWN" and value["backoff_seconds"] == 900
    progressed = controller.failure_decision(failure, audit(ref), previous_units=9,
                                             no_progress_failures=8, attempt=12)
    assert progressed["status"] == "BACKOFF" and progressed["no_progress_failures"] == 0
    assert controller.auto_recovery_policy()["max_gpu_workers"] == 6
    assert controller.auto_recovery_policy()["automatic_followup_authorized"] is False


@pytest.mark.parametrize("classification", [
    "UNKNOWN_FEEDBACK", "STATE_BINDING_FAILURE", "NUMERICAL_FAILURE", "HARD_PEAK_LIMIT", None,
])
def test_unknown_state_numerical_and_peak_failures_are_hard_blocks(root, classification):
    ref = evidence(root)
    result = controller.failure_decision(dict(classification=classification, evidence=[ref]),
        audit(ref), previous_units=10, no_progress_failures=0, attempt=1)
    assert result["status"] == "HARD_BLOCKED"


def test_resource_label_cannot_override_unknown_or_regressed_checkpoint(root):
    ref = evidence(root)
    failure = dict(classification="RETRY_SAFE_RESOURCE", evidence=[ref])
    for value, before in ((audit(ref, unknown=1), 10), (audit(ref), 11)):
        assert controller.failure_decision(failure, value, previous_units=before,
            no_progress_failures=0, attempt=1)["status"] == "HARD_BLOCKED"
    io_failure = controller.launch_failure_record(OSError(errno.EAGAIN, "spawn unavailable"))
    assert io_failure["actual_child_created"] is False
    io_failure["evidence"] = [ref]
    assert controller.failure_decision(io_failure, audit(ref), previous_units=10,
        no_progress_failures=0, attempt=1)["status"] == "BACKOFF"
    io_failure["actual_errno"] = errno.EINVAL
    assert controller.failure_decision(io_failure, audit(ref), previous_units=10,
        no_progress_failures=0, attempt=1)["status"] == "HARD_BLOCKED"


def test_dependencies_require_accepted_actual_exit_not_a_result_file(root):
    queue = controller.Controller.__new__(controller.Controller)
    queue.jobs, queue.accepted = base.core_jobs(parents()), {}
    queue.job_states = {key: controller._initial_state() for key in queue.jobs}
    assert len(queue.ready()) == 6 and all(job["kind"] == "feedback" for job in queue.ready())
    queue.job_states["seed137.feedback_C1"]["status"] = "DRAINING"
    assert not any(job["job_id"] == "seed137.replay_C1" for job in queue.ready())
    queue.accepted["seed137.feedback_C1"] = dict(actual_exit_zero=True)
    queue.job_states["seed137.feedback_C1"]["status"] = "COMPLETE"
    assert any(job["job_id"] == "seed137.replay_C1" for job in queue.ready())
    queue.job_states["seed251.feedback_C05"]["status"] = "HARD_BLOCKED"
    queue._block_dependencies()
    assert queue.job_states["seed251.train_C05"]["status"] == "DEPENDENCY_BLOCKED"
    assert queue.job_states["seed251.feedback_C1"]["status"] == "PENDING"


@pytest.mark.parametrize("status", ["RUNNING", "DRAINING", "DISPATCHING", "SETTLING_EXIT"])
def test_controller_restart_requires_fully_settled_lifecycle(status):
    with pytest.raises(ValueError, match="unsettled dispatch"):
        controller._require_empty_settled_journal(dict(
            active_jobs=[], job_states=dict(job=dict(status=status))))


def test_explicit_stop_and_missing_waitpid_block_restart_before_lease_probe(root, monkeypatch):
    attempt = root / "stages/job/attempts/attempt0001"
    evaluation.publish(attempt / "launch/record.json", dict(pid=123, birth="42949672960"))
    evaluation.publish(root / "journal/state.json", dict(
        protocol_id="protocol", active_jobs=[], job_states={},
        attempt_history=[dict(directory=str(attempt))]))
    monkeypatch.setattr(controller.fcntl, "flock", lambda *args: pytest.fail("no leases before actual-exit proof"))
    with pytest.raises(FileNotFoundError):
        controller.controller_restart_audit(root, dict(id="protocol"))
    (root / "STOP").touch()
    with pytest.raises(ValueError, match="explicit stop"):
        controller.controller_restart_audit(root, dict(id="protocol"))


def test_signal_only_identity_bound_owned_process_with_full_birth(root, monkeypatch):
    queue = base.Controller.__new__(base.Controller)
    queue.runtime = SimpleNamespace(birth=lambda pid: "42949672961")
    child = SimpleNamespace(process=SimpleNamespace(pid=99, poll=lambda: None),
                            birth="42949672960", pidfd=None)
    signals = []
    monkeypatch.setattr(base.os, "kill", lambda pid, number: signals.append((pid, number)))
    with pytest.raises(ValueError, match="reused"):
        queue._signal(child, controller.signal.SIGTERM)
    assert signals == []
    queue.runtime.birth = lambda pid: child.birth
    assert queue._signal(child, controller.signal.SIGTERM)
    assert signals == [(99, controller.signal.SIGTERM)]


def test_launch_uses_new_entry_and_identical_v63_v56_attempt_aliases(root, monkeypatch):
    queue = controller.Controller.__new__(controller.Controller)
    queue.root, queue.protocol = root, dict(id="protocol", cpu_affinity={"0": "0"})
    job = base.core_jobs(parents())["seed137.feedback_C1"]
    queue.jobs, queue.job_states = {job["job_id"]: job}, {job["job_id"]: controller._initial_state()}
    queue.active, queue.attempt_history, queue.accepted = {}, [], {}
    queue._audit = lambda job: dict(resume_allowed=True, unknown_calls=0, progress_units=0,
                                   durable_progress_digest="new", evidence=[])
    queue.journal = lambda: None
    queue.runtime = SimpleNamespace(worker_environment=lambda row: {}, birth=lambda pid: "42949672960")
    captured = {}
    def popen(command, **kwargs):
        captured.update(command=command, **kwargs)
        return SimpleNamespace(pid=2000000000, poll=lambda: None)
    monkeypatch.setattr(controller.subprocess, "Popen", popen)
    monkeypatch.setattr(controller.os, "pidfd_open",
                        lambda pid: (_ for _ in ()).throw(ProcessLookupError()), raising=False)
    lease = (root / "lease.lock").open("a")
    queue.launch(job, (dict(index=0, uuid="GPU-test"), lease, {}))
    assert "finqa_v63_entry.py" in " ".join(captured["command"])
    assert captured["command"][captured["command"].index("--mode") + 1] == "worker"
    assert "--attempt-root" in captured["command"]
    env = captured["env"]
    assert env["V63_ATTEMPT_ID"] == env["V56_ATTEMPT_ID"] == "attempt0001"
    assert env["V63_ATTEMPT_DIR"] == env["V56_ATTEMPT_DIR"]
    assert env["V54_JOB_ID"] == job["job_id"] and env["V54_GPU_LEASE_FD"] == str(lease.fileno())
    assert captured["pass_fds"] == (lease.fileno(),)
    assert queue.job_states[job["job_id"]]["status"] == "RUNNING"
    lease.close()


def test_actual_exit_zero_acceptance_io_wait_does_not_launch_new_science(root):
    queue = controller.Controller.__new__(controller.Controller)
    queue.root, queue.protocol, queue.accepted, queue.explicit_stop = root, dict(id="protocol"), {}, False
    job = base.core_jobs(parents())["seed137.feedback_C1"]
    key = job["job_id"]
    queue.jobs, queue.job_states = {key: job}, {key: dict(controller._initial_state(), attempts=1, status="RUNNING")}
    stable, attempt = queue.job_directory(job), queue.job_directory(job) / "attempts/attempt0001"
    result = evaluation.publish(stable / "result/record.json", dict(status="COMPLETE"))
    evaluation.publish(attempt / "launch/record.json", dict(pid=77, birth="42949672960"))
    lease = (root / "lease.lock").open("a")
    child = base.Child(job=job, gpu=0, uuid="uuid", process=SimpleNamespace(pid=77, poll=lambda: 0),
                      lease=lease, birth="42949672960", pidfd=None, directory=stable, started_epoch=0)
    child.attempt, child.attempt_dir, child.durable_before = 1, attempt, dict(progress_units=0)
    queue.active, queue.journal = {key: child}, lambda: None
    queue._validate_result = lambda child: (_ for _ in ()).throw(OSError(errno.EIO, "temporary read failure"))
    queue.reap()
    assert lease.closed and not queue.active and not queue.accepted
    assert queue.job_states[key]["status"] == "AUDIT_IO_WAIT"
    assert evaluation.checked(attempt / "actual_exit/record.json")["returncode"] == 0
    queue._validate_result = lambda child: result
    queue.job_states[key]["next_eligible_epoch"] = 0
    queue.refresh_deferred_audits()
    assert queue.job_states[key]["status"] == "COMPLETE"
    assert queue.job_states[key]["attempts"] == 1


def test_draw_diagnostics_gate_precedes_new_train_dependency(root):
    queue = base.Controller.__new__(base.Controller)
    queue.root, queue.protocol, queue.parents = root, dict(id="protocol"), parents()
    job = base.core_jobs(parents())["seed137.distribution_C1"]
    child = SimpleNamespace(job=job)
    result = dict(status="COMPLETE", feedback_batch=1, schema="v63_scientific_stage_result.v1",
                  protocol_id="protocol", parent_id="parent-137", seed=137, stage=job["stage"],
                  arm="C1", temperature=1.0, model_released=True, complete_class_tasks=744,
                  complete_class_rows=4974, historical_G_theta_bar_bitwise_equal=True,
                  real_parent_unchanged=True, draw_C_diagnostics_passed=False)
    with pytest.raises(ValueError, match="draw-C"):
        queue._validate_coordinate(child, result)
    result["draw_C_diagnostics_passed"] = True
    queue._validate_coordinate(child, result)


@pytest.mark.parametrize("diagnostic_status", ["COMPLETE", "INCOMPLETE"])
def test_finish_global_generation_barrier_then_score_then_diagnostics(root, monkeypatch, diagnostic_status):
    queue = controller.Controller.__new__(controller.Controller)
    queue.root, queue.protocol = root, dict(id="protocol")
    queue.core = base.core_jobs(parents())
    queue.jobs = dict(queue.core)
    queue.jobs.update({key: dict(job, kind="generate") for key, job in evaluation.planned_jobs().items()})
    queue.accepted = {key: dict(actual_exit=dict(path="/mock", sha256="a" * 64)) for key in queue.jobs}
    queue.active, queue.evaluation_registered, queue.explicit_stop = {}, True, False
    queue.prepared = dict(actual_new_optimizer_budget=1788)
    queue.resource_wait_seconds, queue.attempt_history, queue.job_states = 10.0, [], {}
    queue.status = lambda status: None
    for key, job in queue.jobs.items():
        if job["kind"] != "generate":
            continue
        directory = queue.job_directory(job)
        evaluation.publish(directory / "result/record.json", dict(job_id=key))
        evaluation.publish(directory / "accepted/record.json", dict(job_id=key))
    order = []
    def score(root, panel):
        barrier = evaluation.checked(root / "evaluation_barrier/record.json")
        assert len(barrier["job_results"]) == 24 and barrier["active_children"] == []
        order.append(panel)
        return evaluation.publish(root / "evaluations/panels" / panel / "summary/record.json",
                                  dict(panel=panel, comparisons={"C05-C1": dict(status="COMPLETE")}))
    monkeypatch.setattr(evaluation, "score", score)
    def postrun(root):
        assert len(order) == 3
        order.append("postrun")
        return dict(status=diagnostic_status)
    original_import = controller.importlib.import_module
    monkeypatch.setattr(controller.importlib, "import_module",
                        lambda name: SimpleNamespace(postrun=postrun)
                        if name == "finqa_v63_diagnostics" else original_import(name))
    monkeypatch.setattr(base.stats, "advancement", lambda summary, contracts_complete: dict(
        status="RETAIN_T1_BASELINE", advance=False, contracts_complete=contracts_complete))
    if diagnostic_status != "COMPLETE":
        with pytest.raises(ValueError, match="postrun diagnostics are incomplete"):
            queue.finish()
        assert not (root / "closeout/record.json").exists()
        assert not (root / "promotion/record.json").exists()
    else:
        result = queue.finish()
        assert result["status"] == "COMPLETE" and result["accepted_jobs"] == 48
        assert result["logical_endpoint_conditions"] == 15
        assert result["new_feedback_sessions"] == 4200 and result["new_evaluation_sessions"] == 7458
        assert result["actual_new_optimizer_budget"] == 1788
        assert result["new_logical_sessions"] == 11658 and not result["automatic_followup_started"]


def test_explicit_orphan_stop_never_signals_reused_pid_or_fabricates_exit(root, monkeypatch):
    active, history = [], []
    for pid in (77, 88):
        key = f"job{pid}"
        directory = root / key / "attempts/attempt0001"
        evaluation.publish(directory / "launch/record.json", dict(
            protocol_id="protocol", job=dict(job_id=key), attempt=1, pid=pid, birth="42949672960"))
        active.append(dict(job_id=key, attempt=1, pid=pid, birth="42949672960"))
        history.append(dict(job_id=key, attempt=1, directory=str(directory)))
    evaluation.publish(root / "journal/state.json", dict(
        protocol_id="protocol", active_jobs=active, attempt_history=history))
    births, signals = {77: "42949672960", 88: "42949672961"}, []
    runtime = SimpleNamespace(birth=lambda pid: births.get(pid))
    monkeypatch.setattr(controller, "_same_live_identity", lambda rt, pid, birth: rt.birth(pid) == birth)
    def signal_owned(pid, number):
        signals.append((pid, number))
        births[pid] = None
    monkeypatch.setattr(controller.os, "kill", signal_owned)
    result = controller.stop_orphaned_workers(root, dict(id="protocol"), runtime)
    assert signals == [(77, controller.signal.SIGTERM)] and controller.stop_requested(root)
    assert result["automatic_restart_allowed"] is False
    assert all(row["OS_exitcode"] is None and row["OS_exitcode_independently_observed"] is False
               for row in result["workers"])
