"""Bounded CPU/mock admission, real-exit, recovery and supervisor tests."""
from pathlib import Path
import sys
from types import SimpleNamespace

import pytest

SCRIPTS = str(Path(__file__).resolve().parents[1] / "scripts")
if SCRIPTS not in sys.path:
    sys.path.insert(0, SCRIPTS)
import finqa_v73_binding as binding
import finqa_v73_controller as controller


def job(key="P.shard0"):
    return dict(job_id=key, id=key, model=key[0], shard=int(key[-1]),
        kind="generate", memory_phase="generate", stage="generate", seed=137,
        context_ids=["context"], target_keys=["task"])


def protocol():
    return dict(id="protocol", max_gpu_workers=6, max_workers_per_gpu=1,
        gpu_uuids=controller.base.resource_api.GPU_UUIDS,
        gpu_lease_root=str(controller.base.GPU_LEASE_ROOT), gpu_priority=list(range(8)),
        cpu_affinity={str(gpu): "0-1" for gpu in range(8)},
        jobs={f"{m}.shard{s}": job(f"{m}.shard{s}") for m in "PHL" for s in range(2)},
        model_bindings={m: dict(checkpoint=m) for m in "PHL"},
        final_analysis_resource_policy=controller.cpu_resource_policy())


def audit(progress=0, unknown=0, resume=True):
    return dict(progress_units=progress, unknown_calls=unknown, resume_allowed=resume,
        completed_digest=str(progress), unknown_intents=[])


class Process:
    pid = 987654
    def __init__(self, code=None):
        self.code, self.waits = code, 0
    def poll(self): return self.code
    def wait(self):
        assert self.code is not None
        self.waits += 1
        return self.code


@pytest.fixture
def root(tmp_path, monkeypatch):
    monkeypatch.setattr(binding, "ROOT", tmp_path)
    return tmp_path


def bare_control(root):
    obj = object.__new__(controller.Controller)
    obj.root, obj.protocol = root, protocol()
    obj.jobs, obj.active, obj.accepted, obj.attempt_history = obj.protocol["jobs"], {}, {}, []
    obj.job_states = {key: dict(status="PENDING", attempts=0, no_progress_failures=0,
        progress_units=0, completed_digest="0", next_eligible_epoch=0) for key in obj.jobs}
    obj.stopping, obj.explicit_stop, obj.cpu_analysis = False, False, None
    obj.resource_wait_seconds = 0.0
    obj.journal, obj.status = lambda: None, lambda status: None
    obj.runtime = SimpleNamespace(worker_environment=lambda row: {}, birth=lambda pid: "555",
        host_memory=lambda: dict(available_bytes=200 * controller.GIB))
    obj._audit = lambda job: audit()
    return obj


def child_fixture(control, *, code=None):
    j = control.jobs["P.shard0"]
    stable, closed = control.job_directory(j), []
    process = Process(code)
    child = SimpleNamespace(job=j, process=process, lease=SimpleNamespace(close=lambda: closed.append(True)),
        gpu=6, uuid=control.protocol["gpu_uuids"]["6"], birth="555", pidfd=None,
        directory=stable, attempt_dir=stable / "attempts/attempt0001", attempt=1,
        lifecycle="RUNNING", durable_before=audit())
    control.active[j["job_id"]] = child
    control.job_states[j["job_id"]].update(status="RUNNING", attempts=1)
    return child, closed


def test_frozen_generate_admission_and_host_reservation():
    row = dict(index=6, uuid=protocol()["gpu_uuids"]["6"], free_mib=24 * 1024,
        gpu_isolation=dict(allowed=True, gpu_uuid=protocol()["gpu_uuids"]["6"]))
    assert controller.base.gpu_eligible(row, protocol(), job())
    assert not controller.base.gpu_eligible(dict(row, free_mib=24 * 1024 - 1), protocol(), job())
    assert not controller.base.gpu_eligible(dict(row, gpu_isolation=dict(allowed=False)), protocol(), job())
    assert controller.base.host_requirement("generate", []) == 144 * controller.GIB
    active = [dict(kind="generate", memory=dict(rss_bytes=10 * controller.GIB, peak_rss_bytes=12 * controller.GIB))] * 3
    assert controller.base.host_requirement("generate", active) == 258 * controller.GIB
    assert controller.base.host_requirement("generate", [dict(kind="generate", memory=None)]) is None
    with pytest.raises(ValueError):
        controller.base.gpu_eligible(dict(row, uuid="wrong"), protocol(), job())


def test_constructor_is_fixed_six_jobs_and_single_use(root):
    p = protocol()
    registration = SimpleNamespace(checked_protocol=lambda root: p, checked_implementation=lambda root: {})
    obj = controller.Controller(root, registration=registration, runtime=SimpleNamespace())
    assert set(obj.jobs) == {f"{m}.shard{s}" for m in "PHL" for s in range(2)}
    (root / "journal").mkdir()
    (root / "journal/state.json").write_text("{}")
    with pytest.raises(ValueError, match="single-use"):
        controller.Controller(root, registration=registration, runtime=SimpleNamespace())


@pytest.mark.parametrize("resource,safe,code,unknown,resume,expected", [
    (True, True, 1, 0, True, "BACKOFF"),
    (False, True, 1, 0, True, "HARD_BLOCKED"),
    (True, False, 1, 0, True, "HARD_BLOCKED"),
    (True, True, -9, 0, True, "HARD_BLOCKED"),
    (True, True, -15, 0, True, "HARD_BLOCKED"),
    (True, True, 1, 1, True, "HARD_BLOCKED"),
    (True, True, 1, 0, False, "HARD_BLOCKED"),
])
def test_only_positive_exit_confirmed_resource_failure_is_retryable(resource, safe, code, unknown, resume, expected):
    result = controller.retry_decision(dict(confirmed_resource_failure=resource,
        recoverable_at_actual_return_boundary=safe), audit(3, unknown, resume),
        previous_units=2, no_progress_failures=0, returncode=code)
    assert result["status"] == expected
    if expected == "BACKOFF": assert result["backoff_seconds"] == 300


def test_three_no_progress_failures_stop_and_real_progress_resets_count():
    failure = dict(confirmed_resource_failure=True, recoverable_at_actual_return_boundary=True)
    for count, expected in ((0, "BACKOFF"), (1, "BACKOFF"), (2, "HARD_BLOCKED")):
        result = controller.retry_decision(failure, audit(2), previous_units=2,
            no_progress_failures=count, returncode=1)
        assert result["status"] == expected
    gained = controller.retry_decision(failure, audit(3), previous_units=2,
        no_progress_failures=2, returncode=1)
    assert gained["status"] == "BACKOFF" and gained["no_progress_failures"] == 0
    assert controller.retry_decision(failure, audit(1), previous_units=2,
        no_progress_failures=0, returncode=1)["status"] == "HARD_BLOCKED"


def test_draining_retains_lease_and_worker_slot_until_observed_waitpid(root):
    obj = bare_control(root)
    child, closed = child_fixture(obj)
    result = binding.publish(child.directory / "result/record.json", dict(status="COMPLETE"))
    obj._validate_result = lambda child: result
    obj.reap()
    assert obj.job_states["P.shard0"]["status"] == "DRAINING"
    assert len(obj.active) == 1 and not closed and not obj.accepted
    child.process.code = 0
    obj.reap()
    assert not obj.active and closed == [True] and child.process.waits == 1
    assert obj.accepted["P.shard0"]["actual_exit_zero"]
    actual = binding.checked(child.attempt_dir / "actual_exit/record.json")
    assert actual["returncode"] == 0 and actual["actual_waitpid_observed"]


def test_saved_success_with_nonzero_exit_is_not_accepted(root):
    obj = bare_control(root)
    child, closed = child_fixture(obj, code=1)
    binding.publish(child.directory / "result/record.json", dict(status="COMPLETE"))
    obj.reap()
    assert not obj.accepted and not obj.active and closed == [True]
    assert obj.job_states["P.shard0"]["status"] == "HARD_BLOCKED"


def test_resource_retry_requires_failure_audit_matches_actual_return_state(root):
    obj = bare_control(root)
    child, closed = child_fixture(obj, code=1)
    binding.publish(child.attempt_dir / "failure/record.json", dict(protocol_id="protocol", job_id="P.shard0",
        confirmed_resource_failure=True, recoverable_at_actual_return_boundary=True, durable=audit(1)))
    obj._audit = lambda job: audit(1)
    obj.reap()
    assert obj.job_states["P.shard0"]["status"] == "BACKOFF" and not obj.active
    assert obj.job_states["P.shard0"]["progress_units"] == 1
    decision = binding.checked(child.attempt_dir / "recovery_decision/record.json")
    assert decision["new_sampling_budget"] == 0 and closed == [True]


def test_dispatch_passes_original_lease_fd_and_new_entry(root, monkeypatch):
    obj = bare_control(root)
    monkeypatch.setattr(binding, "install_scientific_paths", lambda: dict(frozen_source_root="/frozen"))
    launches = []
    class P(Process):
        def __init__(self, command, **kwargs):
            super().__init__()
            launches.append((command, kwargs))
    monkeypatch.setattr(controller.subprocess, "Popen", P)
    monkeypatch.setattr(controller.os, "pidfd_open", lambda pid: (_ for _ in ()).throw(ProcessLookupError()), raising=False)
    lease = SimpleNamespace(fileno=lambda: 77, close=lambda: None)
    obj.launch(obj.jobs["P.shard0"], (dict(index=6, uuid=protocol()["gpu_uuids"]["6"]), lease, dict(lease_inode=123)))
    command, options = launches[0]
    assert str(root / "implementation/finqa_v73_entry.py") in command
    assert command[command.index("--mode") + 1] == "worker"
    assert command[command.index("--job") + 1] == "P.shard0"
    assert options["pass_fds"] == (77,)
    assert options["env"]["V54_GPU_LEASE_FD"] == "77"
    assert options["env"]["V73_ATTEMPT_DIR"] == str(root / "jobs/P.shard0/attempts/attempt0001")
    assert obj.active["P.shard0"].birth == "555"


def test_already_accepted_or_backoff_jobs_are_not_ready(root):
    obj = bare_control(root)
    obj.job_states["P.shard0"]["status"] = "COMPLETE"
    obj.job_states["P.shard1"].update(status="BACKOFF", next_eligible_epoch=10**20)
    assert {j["job_id"] for j in obj.ready()} == {"H.shard0", "H.shard1", "L.shard0", "L.shard1"}


def test_stop_marker_has_one_shared_nonresetting_grace(root):
    first = controller._stop_marker(root, protocol(), dict(kind="FAILURE"))
    second = controller._stop_marker(root, protocol(), dict(kind="EXPLICIT"))
    assert first == second and first["reason"]["kind"] == "FAILURE"
    assert first["grace_deadline_epoch"] - first["requested_epoch"] == 600


def test_pid_reuse_is_never_signalled(root, monkeypatch):
    obj = bare_control(root)
    child, _ = child_fixture(obj)
    obj.runtime.birth = lambda pid: "DIFFERENT"
    calls = []
    monkeypatch.setattr(controller.os, "kill", lambda *args: calls.append(args))
    with pytest.raises(ValueError): obj._signal(child, 15)
    assert calls == []


@pytest.mark.parametrize("code,resource_ok,analysis_status", [
    (0, True, "COMPLETE"), (0, True, "COMPLETE_WITH_UNKNOWN"),
    (1, True, "COMPLETE"), (0, False, "COMPLETE")])
def test_cpu_acceptance_needs_actual_exit_and_resources_without_retry(root, monkeypatch, code, resource_ok, analysis_status):
    obj = bare_control(root)
    monkeypatch.setattr(binding, "install_scientific_paths", lambda: dict(frozen_source_root="/frozen"))
    launches = []
    class CPU(Process):
        def __init__(self, command, **kwargs):
            super().__init__(code)
            launches.append((command, kwargs))
            directory = root / "final_analysis/attempt0001"
            binding.publish(root / "final_summary/record.json", dict(status=analysis_status))
            binding.publish(directory / "resources/closeout/record.json", dict(status="COMPLETE",
                protocol_id="protocol", pid=self.pid, birth="555", CUDA_initialized=False,
                all_gates_passed=resource_ok, policy=controller.cpu_resource_policy()))
            binding.publish(directory / "result/record.json", dict(status="COMPLETE", protocol_id="protocol",
                pid=self.pid, resources=binding.entry(directory / "resources/closeout/record.json"),
                analysis=binding.entry(root / "final_summary/record.json")))
    monkeypatch.setattr(controller.subprocess, "Popen", CPU)
    if code == 0 and resource_ok:
        reference, summary = obj._finish_cpu()
        assert summary["status"] == analysis_status
        assert (root / "final_analysis/accepted/record.json").exists()
    else:
        with pytest.raises(ValueError): obj._finish_cpu()
        assert not (root / "final_analysis/accepted/record.json").exists()
    assert len(launches) == 1 and launches[0][1]["env"]["CUDA_VISIBLE_DEVICES"] == ""
    assert "analyze" in launches[0][0]
    with pytest.raises(ValueError, match="never relaunch"): obj._finish_cpu()
    assert len(launches) == 1


def test_final_analysis_cannot_start_before_all_six_actual_exits(root):
    obj = bare_control(root)
    obj._finish_cpu = lambda: pytest.fail("CPU should not launch")
    with pytest.raises(ValueError): obj.finish()


def test_unsettled_dispatch_is_explicit_unknown_not_fabricated_exit(root):
    binding.publish(root / "journal/state.json", dict(protocol_id="protocol", active_jobs=[],
        job_states={"P.shard0": dict(status="DISPATCHING")}, cpu_analysis=None))
    result = controller.stop_orphans(root, protocol(), SimpleNamespace())
    assert not result["all_identities_observed_exited"] and result["workers"] == []
    assert result["unbound_dispatches"][0]["job_id"] == "P.shard0"


@pytest.mark.parametrize("code,closeout,expected", [
    (0, "COMPLETE", "COMPLETE"),
    (1, "COMPLETE", "STOPPED_CONTROLLER_NONZERO_NO_RETRY"),
    (2, "STOPPED_EXPLICIT_REQUEST_NO_AUTO_RESUME", "STOPPED_EXPLICIT_REQUEST_NO_AUTO_RESUME"),
    (-9, None, "STOPPED_CONTROLLER_FAILURE_NO_RETRY"),
])
def test_supervisor_never_restarts_a_controller(root, monkeypatch, code, closeout, expected):
    runtime = SimpleNamespace(birth=lambda pid: "555")
    fake_registration = SimpleNamespace(checked_protocol=lambda root: protocol())
    original_import = controller.importlib.import_module
    monkeypatch.setattr(controller.importlib, "import_module", lambda name:
        fake_registration if name == "finqa_v73_registration" else
        SimpleNamespace(controller_runtime=lambda: runtime) if name == "finqa_v73_resources" else original_import(name))
    monkeypatch.setattr(controller, "_environment", lambda root: dict(CUDA_VISIBLE_DEVICES=""))
    monkeypatch.setattr(controller, "stop_orphans", lambda *args: dict(all_identities_observed_exited=True))
    launches = []
    class CPU(Process):
        def __init__(self, command, **kwargs):
            super().__init__(code); launches.append(command)
            if closeout: binding.publish(root / "closeout/record.json", dict(protocol_id="protocol", status=closeout))
    monkeypatch.setattr(controller.subprocess, "Popen", CPU)
    result = controller.supervise(root)
    assert result["status"] == expected and result["controller_attempts"] == len(launches) == 1
    assert result["automatic_restart_stopped"]
    actual = binding.checked(root / "supervisor/attempts/attempt0001/actual_exit/record.json")
    assert actual["returncode"] == code and actual["actual_waitpid_observed"]
