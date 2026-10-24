"""Focused tests of the new fixed-distribution dispatch and completion boundary."""
from pathlib import Path
import sys
from types import SimpleNamespace

import pytest

SCRIPTS = str(Path(__file__).resolve().parents[1] / "scripts")
if SCRIPTS not in sys.path:
    sys.path.insert(0, SCRIPTS)
import finqa_v71_binding as binding
import finqa_v71_analysis as analysis
import finqa_v71_controller as controller
import finqa_v71_queue_base as queue
import finqa_v71_resources as resources
import finqa_v71_runtime as science


def test_only_two_train_windows_and_three_generations():
    jobs = queue.all_jobs()
    assert len(jobs) == 5 and len(queue.core_jobs()) == 2
    assert {j["kind"] for j in jobs.values()} == {"train", "generate"}
    assert sum(j.get("denominator", 0) for j in jobs.values()) == 1123
    assert jobs["step894.train"]["dependencies"] == []
    assert jobs["step1192.train"]["dependencies"] == ["step894.train"]
    assert jobs["step1192.cal_greedy"]["dependencies"] == ["step894.train"]
    assert jobs["step1490.dev_greedy"]["dependencies"] == ["step1192.train"]
    for step, stage in [(1490, "train"), (894, "distribution"), (894, "replay"), (894, "shard00")]:
        with pytest.raises(ValueError):
            queue.job_spec(step, stage)


@pytest.mark.parametrize("job", list(queue.core_jobs().values()), ids=lambda job: job["job_id"])
def test_runtime_receives_the_registered_fixed_distribution_job(job):
    assert all(job[key] == value for key, value in science.job_spec(job["step"], job["stage"]).items())
    assert resources.kind(job) == "train"


def test_phase_admission_and_immutable_resource_hard_gates():
    row = dict(index=6, uuid=resources.GPU_UUIDS["6"], free_mib=26 * 1024,
        gpu_isolation=dict(allowed=True, gpu_uuid=resources.GPU_UUIDS["6"]))
    protocol, job = dict(gpu_uuids=resources.GPU_UUIDS), queue.job_spec(894, "train")
    assert queue.gpu_eligible(row, protocol, job)
    assert not queue.gpu_eligible(dict(row, free_mib=25 * 1024), protocol, job)
    assert not queue.gpu_eligible(dict(row, gpu_isolation=dict(allowed=False)), protocol, job)
    with pytest.raises(ValueError):
        queue.gpu_eligible(dict(row, uuid="different"), protocol, job)
    policy = resources.resource_policy()
    assert policy["allocated_lifetime_limit_bytes"] == 76 * queue.GIB
    assert policy["boundary_physical_free_reserve_bytes"] == 2 * queue.GIB
    assert policy["other_rss_limit_bytes"] == 192 * queue.GIB
    assert queue.host_requirement("train", []) == 144 * queue.GIB
    assert analysis.resource_policy()["GPU_workers_required_exited"] == 5


def test_draining_retains_gpu_slot_until_actual_exit(tmp_path, monkeypatch):
    monkeypatch.setattr(binding, "ROOT", tmp_path)
    job = queue.job_spec(894, "train")
    stable = queue.job_directory(tmp_path, job)
    attempt = stable / "attempts/attempt0001"
    binding.publish(stable / "result/record.json", {"status": "COMPLETE"})
    code, closed, accepted = [None], [], []
    child = SimpleNamespace(job=job, gpu=6, process=SimpleNamespace(pid=123, poll=lambda: code[0]),
        birth="777", attempt=1, attempt_dir=attempt, directory=stable,
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
    actual = binding.checked(attempt / "actual_exit/record.json")
    assert actual["actual_waitpid_observed"] and actual["returncode"] == 0


@pytest.mark.parametrize("unknown,resume,classification,expected", [
    (0, True, "RETRY_SAFE_RESOURCE", "BACKOFF"),
    (1, True, "RETRY_SAFE_RESOURCE", "HARD_BLOCKED"),
    (0, False, "RETRY_SAFE_RESOURCE", "HARD_BLOCKED"),
    (0, True, "HARD_BLOCK", "HARD_BLOCKED"),
    (0, True, "EXPLICIT_STOP", "HARD_BLOCKED"),
])
def test_only_verified_resource_retry(monkeypatch, unknown, resume, classification, expected):
    monkeypatch.setattr(queue.records, "checked_file", lambda _ref: None)
    audit = dict(resume_allowed=resume, unknown_calls=unknown, progress_units=3,
                 durable_progress_digest="stable", evidence=[])
    result = controller.failure_decision(dict(classification=classification, evidence=[{}]), audit,
        previous_units=2, no_progress_failures=0, attempt=1)
    assert result["status"] == expected


def test_actual_launch_uses_new_entry_and_original_lease(tmp_path, monkeypatch):
    monkeypatch.setattr(binding, "ROOT", tmp_path)
    monkeypatch.setattr(binding, "install_scientific_paths", lambda: {"frozen_source_root": "/frozen"})
    job = queue.core_jobs()["step894.train"]
    control = object.__new__(controller.Controller)
    control.root, control.protocol = tmp_path, dict(id="protocol", cpu_affinity={"6": "0-1"})
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
    def no_pidfd(_pid):
        raise ProcessLookupError()
    monkeypatch.setattr(controller.os, "pidfd_open", no_pidfd, raising=False)
    lease = SimpleNamespace(fileno=lambda: 77, close=lambda: None)
    control.launch(job, (dict(index=6, uuid=resources.GPU_UUIDS["6"]), lease, {}))
    command, kwargs = commands[0]
    assert str(tmp_path / "implementation/finqa_v71_entry.py") in command
    assert command[command.index("--stage") + 1] == "894.train"
    assert kwargs["pass_fds"] == (77,)
    for prefix in ("V71", "V63", "V56"):
        assert kwargs["env"][prefix + "_ATTEMPT_DIR"] == str(
            tmp_path / "points/step0894/train/attempts/attempt0001")


@pytest.mark.parametrize("code,resource_pass", [(0, True), (1, True), (0, False)])
def test_final_cpu_requires_exit_and_resources_and_never_relaunches(tmp_path, monkeypatch, code, resource_pass):
    monkeypatch.setattr(binding, "ROOT", tmp_path)
    monkeypatch.setattr(binding, "install_scientific_paths", lambda: {"frozen_source_root": "/frozen"})
    control = object.__new__(controller.Controller)
    control.root, control.protocol = tmp_path, dict(id="protocol", final_analysis_resource_policy=analysis.resource_policy())
    control.explicit_stop, control.cpu_analysis = False, None
    control.journal, control.status = lambda: None, lambda _: None
    control.runtime = SimpleNamespace(host_memory=lambda: dict(available_bytes=200 * queue.GIB), birth=lambda _: "888")
    launches = []
    class FakeProcess:
        pid = 12345
        def __init__(self, command, **kwargs):
            launches.append((command, kwargs))
            directory = tmp_path / "final_analysis/attempt0001"
            resource = binding.publish(directory / "resources/closeout/record.json", dict(
                status="COMPLETE", protocol_id="protocol", pid=self.pid, birth="888", CUDA_initialized=False,
                all_gates_passed=resource_pass, policy=analysis.resource_policy()))
            binding.publish(directory / "result/record.json", dict(status="COMPLETE", protocol_id="protocol",
                pid=self.pid, analysis=dict(status="COMPLETE", scored=1123),
                resources=binding.entry(directory / "resources/closeout/record.json"), resource_closeout_id=resource["id"]))
        def poll(self):
            return code
        def wait(self):
            return code
    monkeypatch.setattr(controller.subprocess, "Popen", FakeProcess)
    for _ in range(2):
        if code == 0 and resource_pass:
            assert control._finish_cpu() == dict(status="COMPLETE", scored=1123)
        else:
            with pytest.raises(ValueError):
                control._finish_cpu()
    assert len(launches) == 1
    assert launches[0][1]["env"]["CUDA_VISIBLE_DEVICES"] == ""


def test_exact_dose_and_historical_write_protection(tmp_path, monkeypatch):
    import finqa_v71_registration as registration
    policy = registration.scientific_contract()
    assert (policy["new_optimizer_updates"], policy["new_training_task_exposures"],
            policy["new_evaluation_sessions"]) == (596, 2976, 1123)
    assert all(policy[k] == 0 for k in ("new_outer_updates", "new_feedback_sessions",
        "new_class_passes", "new_response_replays", "new_VJPs", "new_terminal_probes"))
    assert policy["original_outer_history"] == [298]
    assert policy["existing_analysis_not_training_start_gate"]
    monkeypatch.setattr(binding, "ROOT", tmp_path / "new")
    with pytest.raises(ValueError):
        binding.publish(tmp_path / "old" / "record.json", {"historical": True})
