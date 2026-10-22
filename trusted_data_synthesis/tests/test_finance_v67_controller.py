"""No-GPU regression checks for bounded residual peers and CPU-only sealing."""
from __future__ import annotations

import copy
from pathlib import Path
from types import SimpleNamespace

import pytest
import finqa_v67_binding as binding

binding.source_module("finqa_v63_entry").install_registered_auxiliary()
import finqa_v67_controller as c


def plan():
    return dict(jobs={f"panel{i}_seed389_C05_b1": dict(job_id=f"panel{i}_seed389_C05_b1",
        seed=389, arm="C05", stage="generate", feedback_batch=1, denominator=n, step=894)
        for i, n in enumerate((883, 120, 120, 120))})


def peer():
    states = {f"j{i}": dict(status="RUNNING" if i < 3 else "HARD_BLOCKED") for i in range(20)}
    prepared = dict(peer_job_roster={k: {} for k in states}, peer_residual_roster=["j0", "j1", "j2"],
                    peer_protocol_id="old")
    journal = dict(protocol_id="old", control_protocol_id="old", job_states=states, updated_epoch=100,
        active_jobs=[dict(job_id=f"j{i}", gpu_index=i) for i in range(3)])
    return journal, prepared


def test_four_exact_jobs_prioritize_dev_without_changing_scientific_order():
    original = plan()
    before = copy.deepcopy(original)
    jobs = c.checked_generation_jobs(original)
    assert len(jobs) == 4 and sum(j["denominator"] for j in jobs.values()) == 1243
    assert original == before
    assert next(j for j in jobs.values() if j["denominator"] == 883)["priority"] == 0
    assert all(j["kind"] == "generate" and not j["dependencies"] for j in jobs.values())


@pytest.mark.parametrize("field,value", [("seed", 251), ("arm", "C1"), ("feedback_batch", 0),
                                          ("step", 745), ("stage", "train"), ("denominator", 884)])
def test_other_science_is_not_authorized(field, value):
    value_plan = plan()
    next(iter(value_plan["jobs"].values()))[field] = value
    with pytest.raises(ValueError):
        c.checked_generation_jobs(value_plan)


def test_three_slots_count_draining_and_do_not_change_old_caps():
    children = {i: SimpleNamespace(gpu=i, lifecycle="DRAINING") for i in range(3)}
    assert c.can_dispatch(children) is False
    assert c.original_base.MAX_WORKERS == 6
    assert c.base.MAX_WORKERS == 3
    children[3] = SimpleNamespace(gpu=3)
    with pytest.raises(ValueError, match="three-worker"):
        c.can_dispatch(children)


def test_fresh_peer_bound_and_stale_wait():
    journal, prepared = peer()
    assert c.checked_peer_snapshot(journal, prepared, now=110)["peer_capacity_bound"] == 3
    assert c.checked_peer_snapshot(journal, prepared, now=161) is None


@pytest.mark.parametrize("change", ["nonresidual_pending", "extra_active", "wrong_roster", "wrong_protocol", "same_gpu"])
def test_peer_cannot_expand_original_residual(change):
    journal, prepared = peer()
    if change == "nonresidual_pending":
        journal["job_states"]["j4"]["status"] = "PENDING"
    elif change == "extra_active":
        journal["active_jobs"].append(dict(job_id="j4", gpu_index=4))
    elif change == "wrong_roster":
        journal["job_states"]["extra"] = dict(status="HARD_BLOCKED")
    elif change == "wrong_protocol":
        journal["protocol_id"] = "other"
    else:
        journal["active_jobs"][0]["gpu_index"] = 1
    with pytest.raises(ValueError):
        c.checked_peer_snapshot(journal, prepared, now=110)


def test_settled_peer_does_not_need_fresh_heartbeat():
    journal, prepared = peer()
    journal["active_jobs"] = []
    for state in journal["job_states"].values():
        state["status"] = "HARD_BLOCKED"
    terminal = dict(protocol_id="old", active_workers=0)
    assert c.checked_peer_snapshot(journal, prepared, terminal=terminal, now=10000)["peer_active_workers"] == 0
    journal["job_states"]["j0"]["status"] = "PENDING"
    with pytest.raises(ValueError):
        c.checked_peer_snapshot(journal, prepared, terminal=terminal, now=10000)


def test_gpu_admission_reserves_full_peer_and_cpu_budget(monkeypatch):
    queue = c.Controller.__new__(c.Controller)
    queue.active, queue._memory = {}, lambda: []
    monkeypatch.setattr(c.original_base, "host_requirement", lambda *args: 100 * c.base.GIB)
    queue.runtime = SimpleNamespace(host_memory=lambda: dict(available_bytes=307 * c.base.GIB))
    assert queue._host_gate(dict(kind="generate")) is None
    queue.runtime.host_memory = lambda: dict(available_bytes=308 * c.base.GIB)
    assert queue._host_gate(dict(kind="generate"))["required_bytes"] == 308 * c.base.GIB


def test_gpu_complete_cannot_finish_while_cpu_pending_or_live():
    queue = c.Controller.__new__(c.Controller)
    queue.jobs = queue.accepted = {"g": {}}
    queue.active, queue.repair_states, queue.repairs_accepted, queue.cpu_active = {}, {"old": {}}, {}, None
    assert not queue._all_work_complete()
    queue.repairs_accepted = {"old": {}}
    queue.cpu_active = SimpleNamespace()
    assert not queue._all_work_complete()
    queue.cpu_active = None
    assert queue._all_work_complete()


def test_cpu_attempt_directory_cannot_overlap_generation(tmp_path, monkeypatch):
    monkeypatch.setattr(c, "ROOT", tmp_path)
    row = dict(job_id="old", attempt=1, directory=str(tmp_path / "repairs/old/attempt0001"))
    assert c.checked_cpu_attempt_directory(row) == Path(row["directory"])
    row["directory"] = str(tmp_path / "evaluations/jobs/old/attempts/attempt0001")
    with pytest.raises(ValueError):
        c.checked_cpu_attempt_directory(row)


@pytest.mark.parametrize("active,status", [(dict(job_id="old"), "RUNNING"), (None, "DISPATCHING")])
def test_cpu_unsettled_blocks_controller_restart(tmp_path, monkeypatch, active, status):
    monkeypatch.setattr(c, "ROOT", tmp_path)
    journal = dict(protocol_id="new", control_protocol_id="new", active_jobs=[], job_states={},
        attempt_history=[], cpu_active=active, repair_states={"old": dict(status=status)}, repair_history=[])
    monkeypatch.setattr(c.evaluation, "checked", lambda path: journal)
    with pytest.raises(ValueError, match="CPU sealing"):
        c.controller_restart_audit(tmp_path, dict(id="new"), dict(id="new"), SimpleNamespace())


def test_cpu_actual_nonzero_remains_nonzero_and_is_not_accepted(tmp_path, monkeypatch):
    queue = c.Controller.__new__(c.Controller)
    queue.root, queue.protocol = tmp_path, dict(id="new")
    queue.cpu_active = SimpleNamespace(job_id="old", process=SimpleNamespace(pid=123, poll=lambda: 1),
        birth="456", directory=tmp_path / "repairs/old/attempt0001", resource_failure=None)
    queue.repair_states, queue.repairs_accepted = {}, {}
    queue.explicit_stop = False
    queue.journal = lambda: None
    records = []
    monkeypatch.setattr(c.evaluation, "publish", lambda path, body: records.append((path, body)))
    monkeypatch.setattr(c, "sealing_api", lambda: pytest.fail("nonzero cannot be accepted"))
    queue._reap_cpu()
    assert queue.cpu_active is None and queue.repair_states["old"]["status"] == "HARD_BLOCKED"
    assert records[0][1]["returncode"] == 1 and records[0][1]["actual_waitpid_observed"] is True


def test_original_frozen_modules_not_patched():
    original = binding.source_module("finqa_v63_controller")
    assert c.inherited is not original
    assert "finqa_v67_worker" in c.inherited.worker_api.__code__.co_consts
    assert "finqa_v63_worker" in original.worker_api.__code__.co_consts
    assert c.lifecycle.stop_orphaned_workers is c.stop_orphaned_workers


def test_lifecycle_waits_for_all_work_and_cpu_blocks_transient_restart():
    import dis
    names = {i.argval for i in dis.get_instructions(c.lifecycle.Controller.run)}
    assert "_all_work_complete" in names and "_all_repairs_terminal" in names and "cpu_active" in names


def test_secondary_lane_can_coexist_with_one_legacy_exclusive_holder_but_not_two_new(tmp_path, monkeypatch):
    import fcntl
    queue = c.Controller.__new__(c.Controller)
    primary, secondary = tmp_path / "primary", tmp_path / "primary/v67-secondary-slot"
    primary.mkdir()
    policy = dict(second_slot_lease_root=str(secondary))
    monkeypatch.setattr(c.binding, "gpu_slot_policy", lambda: policy)
    queue.protocol = dict(gpu_lease_root=str(secondary), legacy_gpu_lease_root=str(primary),
        gpu_slot_policy=policy, gpu_uuids={"0": "uuid0"})
    queue.active, queue.priority = {}, [0]
    queue.peer_admission = lambda: dict(peer_active_workers=1)
    queue._host_gate = lambda job: dict(available_bytes=1000, required_bytes=100)
    row = dict(index=0, uuid="uuid0", free_mib=60 * 1024,
               gpu_isolation=dict(allowed=True, gpu_uuid="uuid0"))
    queue.runtime = SimpleNamespace(inventory=lambda: [row])
    filename = "gpu-" + c.evaluation.digest("uuid0") + ".lock"
    with (primary / filename).open("a") as legacy:
        fcntl.flock(legacy, fcntl.LOCK_EX | fcntl.LOCK_NB)
        acquired = queue.acquire(dict(kind="generate"))
        assert acquired is not None and Path(acquired[2]["lease_path"]).parent == secondary
        assert acquired[2]["per_GPU_total_bound"] == 2
        assert queue.acquire(dict(kind="generate")) is None  # Secondary still held.
        with (primary / filename).open("a") as competing_primary:
            with pytest.raises(BlockingIOError):
                fcntl.flock(competing_primary, fcntl.LOCK_EX | fcntl.LOCK_NB)
        acquired[1].close()
        row["free_mib"] = 23 * 1024
        assert queue.acquire(dict(kind="generate")) is None  # Low utilization never relaxes memory gate.


@pytest.mark.parametrize("launch_exists", [True, False])
def test_orphan_stop_covers_cpu_launch_before_active_journal_or_reports_unknown(tmp_path, monkeypatch, launch_exists):
    monkeypatch.setattr(c, "ROOT", tmp_path)
    directory = tmp_path / "repairs/old/attempt0001"
    (tmp_path / "journal").mkdir()
    (tmp_path / "journal/state.json").write_text("placeholder")
    (directory / "launch").mkdir(parents=True)
    if launch_exists:
        (directory / "launch/record.json").write_text("placeholder")
    journal = dict(protocol_id="new", control_protocol_id="new", active_jobs=[], cpu_active=None,
        attempt_history=[], repair_states={"old": dict(status="DISPATCHING")},
        repair_history=[dict(job_id="old", attempt=1, directory=str(directory))])
    launch = dict(protocol_id="new", control_protocol_id="new", job_id="old", attempt=1, pid=101, birth="202")
    monkeypatch.setattr(c.evaluation, "checked", lambda path: journal if Path(path).name == "state.json" else launch)
    monkeypatch.setattr(c.evaluation, "file_binding", lambda path: dict(path=str(path)))
    monkeypatch.setattr(c.evaluation, "publish", lambda path, body: body)
    alive, signaled = {101}, []
    monkeypatch.setattr(c.inherited, "_same_live_identity", lambda runtime, pid, birth: pid in alive)
    def kill(pid, signum):
        signaled.append((pid, signum))
        alive.discard(pid)
    monkeypatch.setattr(c.os, "kill", kill)
    result = c.stop_orphaned_workers(tmp_path, dict(id="new"), dict(id="new"), SimpleNamespace())
    assert result["old_generation_control_signaled"] is False
    if launch_exists:
        assert result["all_identities_observed_exited"] is True and len(signaled) == 1
        assert result["workers"][0]["CPU_only"] is True
        assert result["workers"][0]["OS_exitcode"] is None
    else:
        assert result["all_identities_observed_exited"] is False and not signaled
        assert len(result["unresolved_cpu_dispatches"]) == 1
