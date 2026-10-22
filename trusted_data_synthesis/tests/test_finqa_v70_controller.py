"""Focused CPU-only admission/lifecycle checks for the new closed-loop entry."""
from __future__ import annotations

import json
from pathlib import Path
import sys
from types import SimpleNamespace

import pytest

SCRIPTS = Path(__file__).resolve().parents[1] / "scripts"
sys.path.insert(0, str(SCRIPTS))
import finqa_v70_binding as binding
import finqa_v70_analysis as analysis
import finqa_v70_controller as controller
import finqa_v70_queue_base as queue
import finqa_v70_resources as resources
import finqa_v70_runtime as science
import finqa_v70_worker as worker


def test_fixed_dag_dose_and_real_endpoint_dependencies():
    jobs = controller.planned_jobs()
    assert len(jobs) == 26
    assert len(queue.core_jobs()) == 23
    assert sum(job["kind"] == "class" for job in jobs.values()) == 12
    assert sum(job["kind"] == "feedback" for job in jobs.values()) == 3
    assert sum(job["kind"] == "train" for job in jobs.values()) == 2
    assert sum(job.get("denominator", 0) for job in jobs.values()) == 1123
    assert "step1490.train" not in jobs
    assert jobs["step1192.shard00"]["dependencies"] == ["step894.train"]
    assert jobs["step1490.shard03"]["dependencies"] == ["step1192.train"]
    assert jobs["step1490.dev_greedy"]["dependencies"] == ["step1192.train"]
    assert jobs["step1192.cal_greedy"]["dependencies"] == ["step894.train"]
    assert set(jobs["step1490.virtual_point"]["dependencies"]) == {
        f"step1490.shard{i:02d}" for i in range(4)}


@pytest.mark.parametrize("job", list(queue.core_jobs().values()), ids=lambda job: job["job_id"])
def test_all_scientific_jobs_match_actual_runtime_contract(job):
    actual = science.job_spec(job["step"], job["stage"])
    assert all(job[key] == value for key, value in actual.items())
    assert resources.kind(job) == ("class_" if job["kind"] == "class" else job["kind"])
    assert queue.job_directory(binding.ROOT, job) == (
        binding.ROOT / "points" / f"step{job['step']:04d}" / job["stage"])


def test_no_unregistered_point_or_third_training_window():
    with pytest.raises(ValueError):
        queue.job_spec(1490, "train")
    with pytest.raises(ValueError):
        queue.job_spec(1788, "virtual_point")


def test_native_cache_policy_preserves_hard_limits_and_original_plan():
    policy = resources.resource_policy()
    protection = resources.memory_protection_policy()
    assert policy["max_gpu_workers"] == 6 and policy["max_workers_per_gpu"] == 1
    assert policy["allocated_lifetime_limit_bytes"] == 76 * queue.GIB
    assert policy["boundary_physical_free_reserve_bytes"] == 2 * queue.GIB
    assert policy["class_rss_limit_bytes"] == 160 * queue.GIB
    assert policy["other_rss_limit_bytes"] == 192 * queue.GIB
    assert protection["maximum_incremental_warm_allocation_bytes"] == 16 * queue.GIB
    assert protection["warm_once_per_cold_worker"] is True
    assert protection["external_holder"] is False
    assert protection["scientific_root"] == str(binding.ROOT)
    assert resources.protection.planned_warm_bytes(free_bytes=80 * queue.GIB,
        allocated_bytes=20 * queue.GIB) == 16 * queue.GIB
    assert resources.protection.planned_warm_bytes(free_bytes=14 * queue.GIB,
        allocated_bytes=20 * queue.GIB) == 0


def test_cache_release_only_when_original_physical_free_gate_fails():
    events, releases = [], []
    guard = object.__new__(resources.ResourceGuard)
    guard.torch = SimpleNamespace(cuda=SimpleNamespace(empty_cache=lambda: releases.append(True)))
    guard._cache_release_count = guard._cache_retained_wait_count = 0
    guard._protection_event = lambda *args, **kwargs: events.append((args, kwargs))
    guard._capacity_cleanup({"free_bytes": 3 * queue.GIB}, free_pass=True)
    assert releases == [] and guard._cache_retained_wait_count == 1
    guard._capacity_cleanup({"free_bytes": queue.GIB}, free_pass=False)
    assert releases == [True] and guard._cache_release_count == 1


def test_shared_gpu_admission_keeps_exact_phase_threshold_and_uuid():
    row = dict(index=6, uuid=resources.GPU_UUIDS["6"], free_mib=24 * 1024,
        gpu_isolation=dict(allowed=True, gpu_uuid=resources.GPU_UUIDS["6"]))
    protocol = dict(gpu_uuids=resources.GPU_UUIDS)
    assert queue.gpu_eligible(row, protocol, queue.job_spec(894, "shard00"))
    assert not queue.gpu_eligible(row, protocol, queue.job_spec(894, "replay"))
    assert queue.gpu_eligible(dict(row, free_mib=56 * 1024), protocol, queue.job_spec(894, "replay"))
    assert not queue.gpu_eligible(dict(row, gpu_isolation=dict(allowed=False)),
                                  protocol, queue.job_spec(894, "shard00"))
    with pytest.raises(ValueError, match="UUID"):
        queue.gpu_eligible(dict(row, uuid="GPU-unregistered"), protocol, queue.job_spec(894, "shard00"))


def test_host_reservation_counts_initialization_and_uncertain_rss():
    assert queue.host_requirement("class", []) == 256 * queue.GIB
    assert queue.host_requirement("replay", [dict(kind="class", memory=None)]) is None
    assert queue.host_requirement("replay", [dict(kind="class",
        memory=dict(rss_bytes=80 * queue.GIB, peak_rss_bytes=90 * queue.GIB))]) == 224 * queue.GIB
    with pytest.raises(ValueError, match="RSS"):
        queue.host_requirement("replay", [dict(kind="class",
            memory=dict(rss_bytes=80 * queue.GIB, peak_rss_bytes=161 * queue.GIB))])


def test_draining_and_initialization_keep_worker_and_gpu_slots():
    active = {str(i): SimpleNamespace(gpu=i, lifecycle="DRAINING" if i % 2 else "INITIALIZING")
              for i in range(6)}
    assert not queue.can_dispatch(active)
    active.pop("5")
    assert queue.can_dispatch(active)
    active["duplicate"] = SimpleNamespace(gpu=0)
    with pytest.raises(ValueError, match="one project worker"):
        queue.can_dispatch(active)


def test_result_file_never_releases_a_draining_worker(tmp_path, monkeypatch):
    monkeypatch.setattr(binding, "ROOT", tmp_path)
    job = queue.job_spec(894, "shard00")
    stable = queue.job_directory(tmp_path, job)
    directory = stable / "attempts/attempt0001"
    binding.publish(stable / "result/record.json", {"status": "COMPLETE"})
    code, closed, accepted = [None], [], []
    child = SimpleNamespace(job=job, gpu=6, process=SimpleNamespace(pid=123, poll=lambda: code[0]),
        birth="777", attempt=1, attempt_dir=directory, directory=stable,
        lease=SimpleNamespace(close=lambda: closed.append(True)), pidfd=None)
    control = object.__new__(controller.Controller)
    control.root, control.protocol = tmp_path, {"id": "protocol"}
    control.active, control.job_states = {job["job_id"]: child}, {job["job_id"]: {"status": "RUNNING"}}
    control.explicit_stop = False
    control.journal = lambda: None
    control._block_dependencies = lambda: None
    control._validate_result = lambda _child: {"status": "COMPLETE"}
    control._accept_result = lambda _child, result: accepted.append(result)
    control.reap()
    assert control.job_states[job["job_id"]]["status"] == "DRAINING"
    assert len(control.active) == 1 and not closed and not accepted
    code[0] = 0
    control.reap()
    assert not control.active and closed == [True] and len(accepted) == 1
    actual = binding.checked(directory / "actual_exit/record.json")
    assert actual["actual_waitpid_observed"] is True and actual["returncode"] == 0


@pytest.mark.parametrize("unknown,resume,classification,expected", [
    (0, True, "RETRY_SAFE_RESOURCE", "BACKOFF"),
    (1, True, "RETRY_SAFE_RESOURCE", "HARD_BLOCKED"),
    (0, False, "RETRY_SAFE_RESOURCE", "HARD_BLOCKED"),
    (0, True, "HARD_BLOCK", "HARD_BLOCKED"),
    (0, True, "EXPLICIT_STOP", "HARD_BLOCKED"),
])
def test_only_verified_resource_retry_not_unknown_or_numeric(monkeypatch, unknown, resume, classification, expected):
    monkeypatch.setattr(queue.records, "checked_file", lambda _ref: None)
    audit = dict(resume_allowed=resume, unknown_calls=unknown, progress_units=3,
                 durable_progress_digest="stable", evidence=[])
    result = controller.failure_decision(dict(classification=classification, evidence=[{}]), audit,
        previous_units=2, no_progress_failures=0, attempt=1)
    assert result["status"] == expected


def _cpu_control(tmp_path, monkeypatch, *, code=0, resource_pass=True):
    monkeypatch.setattr(binding, "ROOT", tmp_path)
    control = object.__new__(controller.Controller)
    control.root = tmp_path
    control.protocol = dict(id="protocol", final_analysis_resource_policy=analysis.resource_policy())
    control.explicit_stop, control.cpu_analysis = False, None
    control.journal = lambda: None
    control.status = lambda _status: None
    control.runtime = SimpleNamespace(host_memory=lambda: dict(available_bytes=200 * queue.GIB),
        birth=lambda _pid: "888")
    monkeypatch.setattr(binding, "install_scientific_paths", lambda: {"frozen_source_root": "/frozen"})
    launches = []

    class FakeProcess:
        pid = 12345
        def __init__(self, command, **kwargs):
            launches.append((command, kwargs))
            directory = tmp_path / "final_analysis/attempt0001"
            resource = binding.publish(directory / "resources/closeout/record.json", dict(
                status="COMPLETE", protocol_id="protocol", pid=self.pid, birth="888", CUDA_initialized=False,
                all_gates_passed=resource_pass, policy=analysis.resource_policy()))
            binding.publish(directory / "result/record.json", dict(status="COMPLETE",
                protocol_id="protocol", pid=self.pid, analysis=dict(status="COMPLETE", scored=1123),
                resources=binding.entry(directory / "resources/closeout/record.json"),
                resource_closeout_id=resource["id"]))
        def poll(self):
            return code
        def wait(self):
            return code

    monkeypatch.setattr(controller.subprocess, "Popen", FakeProcess)
    return control, launches


def test_single_cpu_analysis_actual_waitpid_and_idempotent_reconcile(tmp_path, monkeypatch):
    control, launches = _cpu_control(tmp_path, monkeypatch)
    assert control._finish_cpu() == dict(status="COMPLETE", scored=1123)
    assert control._finish_cpu() == dict(status="COMPLETE", scored=1123)
    assert len(launches) == 1
    assert launches[0][1]["env"]["CUDA_VISIBLE_DEVICES"] == ""
    actual = binding.checked(tmp_path / "final_analysis/attempt0001/actual_exit/record.json")
    assert actual["actual_waitpid_observed"] is True and actual["returncode"] == 0


@pytest.mark.parametrize("code,resource_pass", [(1, True), (0, False)])
def test_cpu_nonzero_or_bad_resource_never_completes_or_relaunches(tmp_path, monkeypatch, code, resource_pass):
    control, launches = _cpu_control(tmp_path, monkeypatch, code=code, resource_pass=resource_pass)
    for _ in range(2):
        with pytest.raises(ValueError):
            control._finish_cpu()
    assert len(launches) == 1
    assert not (tmp_path / "final_analysis/accepted/record.json").exists()


def test_orphan_stop_never_signals_a_different_birth(tmp_path, monkeypatch):
    monkeypatch.setattr(binding, "ROOT", tmp_path)
    directory = tmp_path / "final_analysis/attempt0001"
    binding.publish(directory / "launch/record.json", dict(protocol_id="protocol",
        kind="final_CPU_analysis", pid=123, birth="old_birth"))
    monkeypatch.setattr(controller, "_original_stop_orphaned_workers",
                        lambda *args: dict(all_identities_observed_exited=True))
    monkeypatch.setattr(controller.inherited, "_same_live_identity", lambda *args: False)
    sent = []
    monkeypatch.setattr(controller.os, "kill", lambda *args: sent.append(args))
    result = controller.stop_orphaned_workers(tmp_path, {"id": "protocol"}, object())
    assert result["all_identities_observed_exited"] is True and not sent


def test_response_durable_metadata_requires_joint_draw_counts(tmp_path):
    directory = tmp_path / "checkpoints/response000001"
    directory.mkdir(parents=True)
    (directory / "state.pt").write_bytes(b"actual-durable-byte-placeholder")
    condition = dict(id="condition", identity=dict(point_id="point", parameter_digest="parameters"),
                     ordered_episode_roster=[dict(seed=101)] * 700)
    backend = dict(backend_version=worker.temperature.BACKEND_VERSION,
        feedback_condition_id="condition", temperature=1.0, arm="C1", feedback_batch=1,
        draw_seeds=[101, 103], draw_component_version=worker.temperature.components.VERSION,
        mean_tolerances=worker.temperature.MEAN_TOLERANCES)
    order = [[0, 0, "call"]]
    body = dict(schema="v19_response_boundary_checkpoint.v1", response_prefix_complete=True,
        formal_and_draws_atomically_committed=True, draw_components_schema=worker.temperature.components.VERSION,
        cursor=1, full_replay_complete=True, draw_response_counts={"101": 1, "103": 0},
        state_sha256="a" * 64,
        binding=dict(backend_identity=backend, response_count=1, point_id="point",
            parameter_digest="parameters", denominator=700, gradient_length_normalized=False,
            block_size=8, checkpoint_every_responses=16, replay_state_adapter=worker.temperature.BACKEND_VERSION,
            response_order=order, response_order_sha256=binding.digest(order)))
    path = directory / "record.json"
    path.write_text(json.dumps(dict(body, id=binding.digest(body))))
    assert worker._response_metadata(tmp_path, condition)[0] == 1
    body["draw_response_counts"] = {"101": 0, "103": 1}
    path.write_text(json.dumps(dict(body, id=binding.digest(body))))
    with pytest.raises(ValueError, match="draw counts"):
        worker._response_metadata(tmp_path, condition)


def test_future_context_is_prepared_once_inside_counted_worker_after_actual_exit(tmp_path, monkeypatch):
    import finqa_v70_training as training
    monkeypatch.setattr(binding, "ROOT", tmp_path)
    monkeypatch.setattr(training, "ROOT", tmp_path)
    protocol = binding.publish(tmp_path / "protocol/record.json", {"schema": "test"})
    prior = tmp_path / "points/step0894/train"
    actual = prior / "attempts/attempt0001/actual_exit/record.json"
    binding.publish(actual, dict(protocol_id=protocol["id"], job_id="step894.train",
        actual_waitpid_observed=True, returncode=0))
    binding.publish(prior / "accepted/record.json", dict(protocol_id=protocol["id"],
        job_id="step894.train", actual_exit=binding.entry(actual), actual_exit_zero=True,
        resources_passed=True))
    calls, checks = [], []

    def prepare(root, step, protocol_id):
        calls.append((root, step, protocol_id))
        binding.publish(tmp_path / "points/step1192/context/record.json", {"step": 1192})

    monkeypatch.setattr(training, "prepare_point", prepare)
    guard = SimpleNamespace(stop=SimpleNamespace(requested=False),
                            check=lambda label, **kwargs: checks.append(label))
    worker.prepare_point_for_job(tmp_path, queue.job_spec(1192, "shard00"), guard)
    worker.prepare_point_for_job(tmp_path, queue.job_spec(1192, "shard01"), guard)
    assert len(calls) == 1
    assert checks == ["before_actual_next_point_CPU_registration", "after_actual_next_point_CPU_registration"]


def test_completed_file_without_actual_exit_acceptance_cannot_prepare_next_point(tmp_path, monkeypatch):
    import finqa_v70_training as training
    monkeypatch.setattr(binding, "ROOT", tmp_path)
    monkeypatch.setattr(training, "ROOT", tmp_path)
    binding.publish(tmp_path / "points/step0894/train/completed/record.json", {"status": "COMPLETE"})
    called = []
    monkeypatch.setattr(training, "prepare_point", lambda *args: called.append(args))
    with pytest.raises(FileNotFoundError):
        worker.prepare_point_for_job(tmp_path, queue.job_spec(1192, "shard00"),
            SimpleNamespace(stop=SimpleNamespace(requested=False)))
    assert not called


@pytest.mark.parametrize("stage", ["shard00", "virtual_point", "replay", "distribution", "train"])
def test_restart_audit_allows_undispatched_future_dependencies(tmp_path, monkeypatch, stage):
    import finqa_v70_training as training
    monkeypatch.setattr(binding, "ROOT", tmp_path)
    monkeypatch.setattr(training, "ROOT", tmp_path)
    binding.publish(tmp_path / "protocol/record.json", {"schema": "test"})
    audit = worker.audit_job_resume(tmp_path, queue.job_spec(1192, stage))
    assert audit["resume_allowed"] and audit["progress_units"] == audit["unknown_calls"] == 0
    assert audit["details"]["awaiting_registered_previous_training"]


def test_missing_context_cannot_hide_a_previously_computed_class_task(tmp_path, monkeypatch):
    import finqa_v70_training as training
    monkeypatch.setattr(binding, "ROOT", tmp_path)
    monkeypatch.setattr(training, "ROOT", tmp_path)
    binding.publish(tmp_path / "protocol/record.json", {"schema": "test"})
    (tmp_path / "points/step1192/task_cache/task0001").mkdir(parents=True)
    with pytest.raises(ValueError, match="missing context"):
        worker.audit_job_resume(tmp_path, queue.job_spec(1192, "shard00"))


def test_dispatched_pre_context_resource_failure_can_resume_only_from_accepted_parent(tmp_path, monkeypatch):
    import finqa_v70_training as training
    monkeypatch.setattr(binding, "ROOT", tmp_path)
    monkeypatch.setattr(training, "ROOT", tmp_path)
    protocol = binding.publish(tmp_path / "protocol/record.json", {"schema": "test"})
    point = tmp_path / "points/step1192"
    (point / "shard00/attempts/attempt0001").mkdir(parents=True)
    (point / "shard00/worker.lock").touch()
    binding.publish(point / "task_plan/record.json", {"stage": "partially_published_CPU_metadata"})
    with pytest.raises(FileNotFoundError):
        worker.audit_job_resume(tmp_path, queue.job_spec(1192, "shard00"))
    prior = tmp_path / "points/step0894/train"
    actual = prior / "attempts/attempt0001/actual_exit/record.json"
    binding.publish(actual, dict(protocol_id=protocol["id"], job_id="step894.train",
        actual_waitpid_observed=True, returncode=0))
    binding.publish(prior / "accepted/record.json", dict(protocol_id=protocol["id"],
        job_id="step894.train", actual_exit=binding.entry(actual), actual_exit_zero=True,
        resources_passed=True))
    audit = worker.audit_job_resume(tmp_path, queue.job_spec(1192, "shard00"))
    assert audit["resume_allowed"] and audit["progress_units"] == 0 and audit["unknown_calls"] == 0
    (point / "shard00/payload").mkdir()
    with pytest.raises(ValueError, match="missing context"):
        worker.audit_job_resume(tmp_path, queue.job_spec(1192, "shard00"))


def test_actual_launch_routes_point_and_all_attempt_aliases_to_new_entry(tmp_path, monkeypatch):
    monkeypatch.setattr(binding, "ROOT", tmp_path)
    monkeypatch.setattr(binding, "install_scientific_paths", lambda: {"frozen_source_root": "/frozen"})
    job = queue.core_jobs()["step894.shard00"]
    control = object.__new__(controller.Controller)
    control.root = tmp_path
    control.protocol = dict(id="protocol", cpu_affinity={"6": "0-1"})
    control.job_states = {job["job_id"]: controller.inherited._initial_state()}
    control.jobs, control.active, control.attempt_history = {job["job_id"]: job}, {}, []
    control.journal = lambda: None
    control._audit = lambda _job: dict(resume_allowed=True, unknown_calls=0, progress_units=0,
        durable_progress_digest="zero", evidence=[])
    control.runtime = SimpleNamespace(worker_environment=lambda _row: {}, birth=lambda _pid: "555")
    commands = []
    class FakeProcess:
        pid = 987654
        def __init__(self, command, **kwargs):
            commands.append((command, kwargs))
        def poll(self):
            return None
    monkeypatch.setattr(controller.subprocess, "Popen", FakeProcess)
    def unavailable_pidfd(_pid):
        raise ProcessLookupError()
    monkeypatch.setattr(controller.os, "pidfd_open", unavailable_pidfd, raising=False)
    lease = SimpleNamespace(fileno=lambda: 77, close=lambda: None)
    control.launch(job, (dict(index=6, uuid=resources.GPU_UUIDS["6"]), lease, {}))
    command, kwargs = commands[0]
    assert str(tmp_path / "implementation/finqa_v70_entry.py") in command
    assert command[command.index("--stage") + 1] == "894.shard00"
    assert kwargs["pass_fds"] == (77,)
    for prefix in ("V70", "V63", "V56"):
        assert kwargs["env"][prefix + "_ATTEMPT_DIR"] == str(
            tmp_path / "points/step0894/shard00/attempts/attempt0001")
    assert kwargs["env"]["V54_JOB_ID"] == "step894.shard00"
    assert len(control.active) == 1


def test_reused_complete_feedback_accepts_zero_new_calls_without_changing_logical_dose(tmp_path, monkeypatch):
    import finqa_v70_training as training
    monkeypatch.setattr(binding, "ROOT", tmp_path)
    protocol = binding.publish(tmp_path / "protocol/record.json", {"schema": "test"})
    monkeypatch.setattr(training, "checked_point", lambda *args: {"id": "point"})
    job = queue.job_spec(894, "virtual_point")
    result = dict(schema="v70_scientific_stage_result.v1", status="COMPLETE",
        protocol_id=protocol["id"], job_id=job["job_id"], seed=137, step=894,
        stage="virtual_point", model_released=True, resources={"all_gates_passed": True},
        point_context_id="point", denominator=700, total_feedback_sessions=700,
        new_feedback_sessions=700, new_feedback_sessions_is_logical_condition_total_not_new_attempt=True,
        new_actual_response_calls=0, real_parent_unchanged=True)
    worker.validate_result(tmp_path, job, result)
    with pytest.raises(ValueError, match="700-session"):
        worker.validate_result(tmp_path, job, dict(result, denominator=350))
