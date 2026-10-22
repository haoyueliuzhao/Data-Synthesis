"""CPU-only checks for disjoint, unscored five-endpoint generation control."""
from __future__ import annotations

import copy
from pathlib import Path
from types import SimpleNamespace

import pytest

import finqa_v65_binding as binding

binding.source_module("finqa_v63_entry").install_registered_auxiliary()
import finqa_v65_controller as controller


def plan_fixture():
    jobs = {}
    for seed, arm in binding.ELIGIBLE_COORDINATES:
        for index, count in enumerate((259, 259, 350, 375)):
            key = f"panel{index}_seed{seed}_{arm}_b1"
            jobs[key] = dict(job_id=key, seed=seed, arm=arm, stage="generate", feedback_batch=1,
                             denominator=count, step=894)
    return dict(jobs=jobs)


def test_exact_twenty_generation_jobs_and_no_core_dependencies():
    plan = plan_fixture()
    before = copy.deepcopy(plan)
    jobs = controller.checked_generation_jobs(plan)
    assert len(jobs) == 20 and sum(j["denominator"] for j in jobs.values()) == 6215
    assert all(j["kind"] == "generate" and j["dependencies"] == [] for j in jobs.values())
    assert plan == before


@pytest.mark.parametrize("change", ["failed_branch", "extra", "dose", "stage", "step", "batch"])
def test_unregistered_generation_or_core_work_is_rejected(change):
    plan = plan_fixture()
    first = next(iter(plan["jobs"].values()))
    if change == "failed_branch":
        first.update(seed=389, arm="C05")
    elif change == "extra":
        plan["jobs"]["extra"] = dict(first, job_id="extra")
    elif change == "dose":
        first["denominator"] += 1
    elif change == "stage":
        first["stage"] = "train_C1"
    elif change == "step":
        first["step"] = 745
    else:
        first["feedback_batch"] = 0
    with pytest.raises(ValueError):
        controller.checked_generation_jobs(plan)


def test_five_slots_include_initializing_and_draining_and_preserve_original_six_cap():
    children = {str(i): SimpleNamespace(gpu=i, lifecycle="DRAINING") for i in range(5)}
    assert not controller.can_dispatch(children)
    assert controller.original_base.MAX_WORKERS == 6
    assert controller.base.MAX_WORKERS == 5
    children["5"] = SimpleNamespace(gpu=5, lifecycle="INITIALIZING")
    with pytest.raises(ValueError, match="five-worker"):
        controller.can_dispatch(children)
    children.pop("5")
    children["4"].gpu = 0
    with pytest.raises(ValueError, match="one experiment"):
        controller.can_dispatch(children)


def test_admission_retains_original_math_plus_full_peer_reservation(monkeypatch):
    queue = controller.Controller.__new__(controller.Controller)
    queue.active = {}
    queue._memory = lambda: []
    monkeypatch.setattr(controller.original_base, "host_requirement", lambda kind, active: 100 * controller.base.GIB)
    queue.runtime = SimpleNamespace(host_memory=lambda: dict(available_bytes=163 * controller.base.GIB))
    assert queue._host_gate(dict(kind="generate")) is None
    queue.runtime.host_memory = lambda: dict(available_bytes=164 * controller.base.GIB)
    admission = queue._host_gate(dict(kind="generate"))
    assert admission["required_bytes"] == 164 * controller.base.GIB
    assert admission["reserved_other_control_startup_gib"] == 64
    assert admission["other_control_actual_RSS_not_deducted"] is True


def test_no_sixth_generation_dispatch_even_if_peer_has_no_worker():
    queue = controller.Controller.__new__(controller.Controller)
    queue.active = {str(i): SimpleNamespace(gpu=i) for i in range(5)}
    assert queue.acquire(dict(kind="generate")) is None


def test_core_training_barrier_is_unreachable():
    queue = controller.Controller.__new__(controller.Controller)
    with pytest.raises(ValueError, match="cannot unlock"):
        queue.seal_training()


def test_attempt_must_stay_in_new_generation_root(tmp_path, monkeypatch):
    monkeypatch.setattr(controller, "ROOT", tmp_path)
    row = dict(job_id="job", attempt=2, directory=str(tmp_path / "evaluations/jobs/job/attempts/attempt0002"))
    assert controller.checked_attempt_directory(row) == Path(row["directory"])
    for bad in (tmp_path / "stages/job/attempts/attempt0002",
                tmp_path / "evaluations/jobs/other/attempts/attempt0002",
                tmp_path / "evaluations/jobs/job/attempts/attempt0001"):
        with pytest.raises(ValueError):
            controller.checked_attempt_directory(dict(row, directory=str(bad)))


def test_missing_actual_exit_cannot_be_inferred(tmp_path, monkeypatch):
    monkeypatch.setattr(controller, "ROOT", tmp_path)
    row = dict(job_id="job", attempt=1, directory=str(tmp_path / "evaluations/jobs/job/attempts/attempt0001"))
    directory = Path(row["directory"])
    (directory / "launch").mkdir(parents=True)
    (directory / "launch/record.json").write_text("placeholder")
    launch = dict(protocol_id="p", job=dict(job_id="job"), attempt=1, pid=123, birth="456")
    monkeypatch.setattr(controller.inherited, "_same_live_identity", lambda *args: False)
    def checked(path):
        if Path(path).parent.name == "launch":
            return launch
        raise FileNotFoundError(path)
    monkeypatch.setattr(controller.evaluation, "checked", checked)
    with pytest.raises(FileNotFoundError):
        controller.audit_attempt_exit(row, dict(id="p"), SimpleNamespace())


def test_generation_finish_is_not_scientific_complete_or_scoring(tmp_path, monkeypatch):
    queue = controller.Controller.__new__(controller.Controller)
    queue.root, queue.control_root = tmp_path, tmp_path
    queue.protocol = queue.control_protocol = dict(id="new")
    queue.scientific_protocol = dict(id="science")
    queue.plan = dict(id="plan")
    queue.jobs = controller.checked_generation_jobs(plan_fixture())
    queue.active, queue.explicit_stop, queue.attempt_history = {}, False, []
    queue.resource_wait_seconds = 123
    queue.accepted = {key: dict(job_id=key, actual_exit_zero=True, actual_exit=dict(key=key)) for key in queue.jobs}
    queue.journal = lambda: None
    states = []
    queue.status = states.append
    monkeypatch.setattr(controller.binding, "read_ref", lambda ref: dict(job_id=ref["key"], returncode=0,
                                                                          actual_waitpid_observed=True))
    monkeypatch.setattr(controller.evaluation, "file_binding", lambda path: dict(path=str(path)))
    monkeypatch.setattr(controller.evaluation, "publish", lambda path, body: body)
    monkeypatch.setattr(controller.evaluation, "score", lambda *args: pytest.fail("early scoring is forbidden"))
    result = queue.finish()
    assert result["status"] == controller.SEALED_STATUS
    assert result["generation_sessions"] == 6215 and result["scoring_calls"] == 0
    assert result["global_scientific_experiment_complete"] is False
    assert result["global_scoring_authorized"] is False
    assert states == [controller.SEALED_STATUS]


def test_sealed_status_never_hides_controller_nonzero_exit():
    sealed = dict(status=controller.SEALED_STATUS)
    assert controller.controller_closeout_status(sealed, 0) == controller.SEALED_STATUS
    assert controller.controller_closeout_status(sealed, 2) == "CONTROLLER_NONZERO_AFTER_CLOSEOUT"


def test_restart_audit_never_demands_healthy_peer_gpu_leases(tmp_path, monkeypatch):
    monkeypatch.setattr(controller, "ROOT", tmp_path)
    journal = dict(protocol_id="new", control_protocol_id="new", active_jobs=[],
        job_states={"job": dict(status="PENDING")}, attempt_history=[dict(job_id="job", attempt=1)])
    monkeypatch.setattr(controller.evaluation, "checked", lambda path: journal)
    observed = []
    monkeypatch.setattr(controller, "audit_attempt_exit", lambda row, protocol, runtime: observed.append(row))
    monkeypatch.setattr(controller.lifecycle.fcntl, "flock", lambda *args: pytest.fail("peer may hold its GPU lease"))
    result = controller.controller_restart_audit(tmp_path, dict(id="new"), dict(id="new"), SimpleNamespace())
    assert result is journal and observed == journal["attempt_history"]
    assert controller.lifecycle.controller_restart_audit is controller.controller_restart_audit


@pytest.mark.parametrize("status", ["RUNNING", "DRAINING", "DISPATCHING", "SETTLING_EXIT"])
def test_parallel_peer_does_not_excuse_own_unsettled_dispatch(tmp_path, monkeypatch, status):
    monkeypatch.setattr(controller, "ROOT", tmp_path)
    journal = dict(protocol_id="new", control_protocol_id="new", active_jobs=[],
        job_states={"job": dict(status=status)}, attempt_history=[])
    monkeypatch.setattr(controller.evaluation, "checked", lambda path: journal)
    with pytest.raises(ValueError, match="unsettled dispatch"):
        controller.controller_restart_audit(tmp_path, dict(id="new"), dict(id="new"), SimpleNamespace())


def test_private_worker_routing_does_not_patch_original_queue():
    original = binding.source_module("finqa_v63_controller")
    assert controller.inherited is not original
    assert "finqa_v65_worker" in controller.inherited.worker_api.__code__.co_consts
    assert "finqa_v63_worker" in original.worker_api.__code__.co_consts
    assert controller.lifecycle.Controller is controller.Controller


def test_science_owner_is_shared_but_local_owner_exclusive(tmp_path, monkeypatch):
    science, control = tmp_path / "science", tmp_path / "science/early"
    control.mkdir(parents=True)
    monkeypatch.setattr(controller.lifecycle, "SCIENTIFIC_ROOT", science)
    queue = controller.Controller.__new__(controller.Controller)
    queue.root = queue.control_root = control
    queue.controller_directory = control / "controllers/attempt0001"
    queue.protocol = queue.control_protocol = dict(id="new")
    queue.controller_attempt = 1
    queue.runtime = SimpleNamespace(birth=lambda pid: "123")
    queue.journal = queue.reap = queue.refresh_deferred_audits = lambda: None
    queue.evaluation_registered, queue.active, queue.jobs, queue.accepted = True, {}, {}, {}
    queue.finish = lambda: dict(status=controller.SEALED_STATUS)
    queue.explicit_stop = False
    locks = []
    monkeypatch.setattr(controller.lifecycle.fcntl, "flock", lambda stream, operation: locks.append((Path(stream.name), operation)))
    monkeypatch.setattr(controller.evaluation, "publish", lambda path, body: body)
    assert queue.run()["status"] == controller.SEALED_STATUS
    assert locks == [(science / "owner.lock", controller.lifecycle.fcntl.LOCK_SH | controller.lifecycle.fcntl.LOCK_NB),
                     (control / "owner.lock", controller.lifecycle.fcntl.LOCK_EX | controller.lifecycle.fcntl.LOCK_NB)]
