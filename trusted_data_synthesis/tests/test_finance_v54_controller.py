from types import SimpleNamespace

import pytest

import finqa_v54_controller as controller
import finqa_v54_evaluation as evaluation


def parents():
    return {str(seed): dict(seed=seed, id=f"p{seed}",
        old_class_context={} if seed == 389 else None,
        new_class_task_count=0 if seed == 389 else 744, c1_reuse=dict(eligible=True))
        for seed in (137, 251, 389)}


def test_core_dag_has_exact_dose_and_actual_dependency_gates():
    jobs = controller.core_jobs(parents())
    assert len(jobs) == 23
    assert sum(j["kind"] == "class" for j in jobs.values()) == 8
    assert not any(j["stage"].startswith("shard") and j["seed"] == 389 for j in jobs.values())
    assert sum(j["kind"] == "train" for j in jobs.values()) == 6
    assert not any(j["stage"] == "train_C1" for j in jobs.values())
    ready = controller.ready_jobs(jobs, {}, set())
    assert [j["stage"] for j in ready[:3]] == ["feedback_C05"] * 3
    assert "seed137.replay_C05" not in {j["job_id"] for j in ready}
    accepted = {"seed137.feedback_C05": {}}
    ready = controller.ready_jobs(jobs, accepted, {"seed137.feedback_C05"})
    assert "seed137.replay_C05" in {j["job_id"] for j in ready}
    accepted["seed137.replay_C05"] = {}
    assert "seed137.distribution_C05" not in {
        j["job_id"] for j in controller.ready_jobs(jobs, accepted, set())}
    accepted.update({f"seed137.shard{i:02d}": {} for i in range(4)})
    assert "seed137.distribution_C05" in {
        j["job_id"] for j in controller.ready_jobs(jobs, accepted, set())}


def test_nonreusable_control_adds_exactly_one_original_window():
    items = parents()
    items["251"]["c1_reuse"]["eligible"] = False
    jobs = controller.core_jobs(items)
    assert len(jobs) == 24
    assert jobs["seed251.train_C1"]["dependencies"] == []


def test_initializing_and_draining_both_count_toward_four_worker_cap():
    active = {str(i): SimpleNamespace(gpu=i, lifecycle=state) for i, state in enumerate(
        ("INITIALIZING", "WAITING", "RUNNING", "DRAINING"))}
    assert controller.can_dispatch(active) is False
    active.pop("3")
    assert controller.can_dispatch(active) is True
    active["3"] = SimpleNamespace(gpu=2)
    with pytest.raises(ValueError, match="more than one"):
        controller.can_dispatch(active)


def test_live_rss_startup_reservations_and_disappearing_process_are_distinct():
    gib = controller.GIB
    active = [dict(kind="replay", memory=dict(rss_bytes=20*gib, peak_rss_bytes=25*gib)),
              dict(kind="class", memory=dict(rss_bytes=100*gib, peak_rss_bytes=110*gib))]
    assert controller.host_requirement("train", active) == (96 + 48 + 28 + 60) * gib
    assert controller.host_requirement("train", [dict(kind="replay", memory=None)]) is None
    with pytest.raises(ValueError, match="RSS hard gate"):
        controller.host_requirement("train", [dict(kind="train",
            memory=dict(rss_bytes=10*gib, peak_rss_bytes=193*gib))])


def test_shared_gpu_admission_requires_registered_uuid_and_stage_capacity():
    protocol = dict(gpu_uuids={str(i): f"uuid{i}" for i in range(8)})
    row = dict(index=2, uuid="uuid2", free_mib=56*1024, processes=["another_project"])
    assert controller.gpu_eligible(row, protocol, dict(kind="replay")) is True
    row["free_mib"] -= 1
    assert controller.gpu_eligible(row, protocol, dict(kind="replay")) is False
    row["uuid"] = "changed"
    with pytest.raises(ValueError, match="UUID"):
        controller.gpu_eligible(row, protocol, dict(kind="class"))


def test_result_without_real_exit_only_enters_draining():
    process = SimpleNamespace(poll=lambda: None)
    assert controller.process_state(process, True) == ("DRAINING", None)
    assert controller.process_state(process, False) == ("RUNNING", None)
    process.poll = lambda: 0
    assert controller.process_state(process, True) == ("EXITED_SUCCESS", 0)


def test_reap_accepts_only_after_exit_and_does_not_read_disappeared_rss(tmp_path):
    control = controller.Controller.__new__(controller.Controller)
    control.protocol, control.active, control.accepted, control.stop_reason = dict(id="protocol"), {}, {}, None
    directory = tmp_path / "job"
    result = evaluation.publish(directory / "result/record.json", dict(status="COMPLETE"))
    control._validate_result = lambda child: result
    control.runtime = SimpleNamespace(process_memory=lambda pid: pytest.fail("RSS read after actual exit"))
    code = [None]
    lease = (tmp_path / "lease.lock").open("a")
    child = controller.Child(job=dict(job_id="job"), gpu=0, uuid="uuid", birth="birth",
        process=SimpleNamespace(pid=123, poll=lambda: code[0]), lease=lease, pidfd=None,
        directory=directory, started_epoch=0)
    control.active["job"] = child
    control.reap()
    assert child.lifecycle == "DRAINING" and control.accepted == {} and not lease.closed
    code[0] = 0
    control.reap()
    assert not control.active and control.accepted["job"]["actual_exit_zero"] is True and lease.closed


def test_dispatch_inherits_existing_lease_fd_and_frozen_source(tmp_path, monkeypatch):
    control = controller.Controller.__new__(controller.Controller)
    control.root, control.launched, control.active = tmp_path, set(), {}
    control.protocol = dict(id="protocol", cpu_affinity={"0": "0-3"})
    control.runtime = SimpleNamespace(worker_environment=lambda row: {}, birth=lambda pid: "birth")
    child = SimpleNamespace(pid=123, poll=lambda: None)
    seen = {}
    def popen(command, **kwargs):
        seen.update(command=command, **kwargs)
        return child
    monkeypatch.setattr(controller.subprocess, "Popen", popen)
    monkeypatch.setattr(controller.os, "pidfd_open", lambda pid: None, raising=False)
    lease = (tmp_path / "original-project-lease.lock").open("a")
    job = controller.core_jobs(parents())["seed137.feedback_C05"]
    control.launch(job, (dict(index=0, uuid="uuid"), lease, dict(lease_inode=123)))
    assert seen["pass_fds"] == (lease.fileno(),)
    assert seen["env"]["V54_GPU_LEASE_FD"] == str(lease.fileno())
    assert seen["env"]["PYTHONPATH"].endswith(str(evaluation.FROZEN_SOURCE))
    assert seen["env"]["CUDA_VISIBLE_DEVICES"] == "uuid"
    assert seen["command"][:3] == ["/usr/bin/taskset", "--cpu-list", "0-3"]
    lease.close()


def test_teardown_identity_gap_does_not_signal_or_drop_lease():
    control = controller.Controller.__new__(controller.Controller)
    control.runtime = SimpleNamespace(birth=lambda pid: None)
    child = SimpleNamespace(process=SimpleNamespace(pid=123, poll=lambda: None), birth="known")
    assert control._signal(child, 15) is False


def test_actual_final_resource_closeout_is_required_for_success(tmp_path):
    control = controller.Controller.__new__(controller.Controller)
    control.root, control.protocol = tmp_path, dict(id="protocol")
    control.parents = parents()
    job = controller.core_jobs(parents())["seed137.feedback_C05"]
    resources = dict(all_gates_passed=True, single_process_lifetime_includes_loading=True)
    directory = tmp_path / "stage"
    evaluation.publish(directory / "result/record.json", dict(
        schema="v54_scientific_stage_result.v1", status="COMPLETE", protocol_id="protocol",
        parent_id="p137", seed=137, stage="feedback_C05", gpu_index=0, resources=resources,
        model_released=True, denominator=700, new_feedback_sessions=700, temperature=0.5,
        real_parent_unchanged=True))
    child = SimpleNamespace(job=job, directory=directory, process=SimpleNamespace(pid=123), gpu=0)
    closeout = tmp_path / "resources/seed137.feedback_C05/pid123/closeout/record.json"
    evaluation.publish(closeout, dict(protocol_id="protocol", job_id=job["job_id"], pid=123,
        gpu_index=0, status="COMPLETE", resources={**resources, "final_boundary_observed": True}))
    with pytest.raises(ValueError, match="final resource boundary"):
        control._validate_result(child)
