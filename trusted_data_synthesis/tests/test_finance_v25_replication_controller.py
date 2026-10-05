"""Small CPU-only fault tests; never load scientific workers, CUDA or test data."""

import hashlib
import importlib.util
from pathlib import Path
from types import SimpleNamespace

import pytest

SCRIPT = Path(__file__).resolve().parents[1] / "scripts/finqa_v25_replication_controller.py"
SPEC = importlib.util.spec_from_file_location("v25_replication_controller_tests", SCRIPT)
controller = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(controller)


def forbid(*args, **kwargs):
    raise AssertionError("CPU fixture must not invoke a real process, GPU or scientific module")


@pytest.fixture
def setup_controller(tmp_path, monkeypatch):
    root = tmp_path / "v25_training_replication_01"
    implementation = root / "implementation"
    implementation.mkdir(parents=True)
    hashes = {}
    for name in controller.FILES:
        raw = ("# CPU fixture " + name + "\n").encode()
        (implementation / name).write_bytes(raw)
        hashes[name] = hashlib.sha256(raw).hexdigest()
    manifest = controller.publish(
        implementation / "record.json",
        {"source_commit": "a" * 40, "sha256": hashes},
    )
    refs = {}
    for branch in ("training_replication", "c_only_test_extension", "replication_evaluation"):
        path = root / branch / "registration/record.json"
        controller.publish(path, {"branch": branch, "applicable": True})
        refs[branch] = controller.entry(path)
    rows = [
        dict(index=i, uuid=f"CPU-GPU-{i}", free_mib=65536, cpu_affinity="0-3") for i in range(8)
    ]
    plan = controller.publish(
        root / "protocol/record.json",
        {
            "implementation_id": manifest["id"],
            "training_registration": refs["training_replication"],
            "extension_registration": refs["c_only_test_extension"],
            "replication_evaluation_registration": refs["replication_evaluation"],
            "api_model": "deepseek-flash",
            "API_calls_authorized": 0,
            "jobs": controller.make_jobs(root),
            "budgets": controller.budgets(),
            "memory_floors_mib": controller.MEMORY_FLOORS,
            "dispatch_disk_floor_bytes": controller.MIN_LAUNCH_DISK_BYTES,
            "gpu_uuids": {str(row["index"]): row["uuid"] for row in rows},
            "cpu_affinity": {str(row["index"]): row["cpu_affinity"] for row in rows},
        },
    )
    monkeypatch.setattr(controller, "ROOT", root)
    monkeypatch.setattr(controller, "__file__", str(implementation / controller.FILES[0]))
    monkeypatch.setattr(controller, "disk_available", lambda root: 800 * 1024**3)
    monkeypatch.setattr(controller, "cpu_command", forbid)
    monkeypatch.setattr(controller, "inventory", forbid)
    monkeypatch.setattr(controller, "load_module", forbid)
    monkeypatch.setattr(controller.subprocess, "Popen", forbid)
    monkeypatch.setattr(controller, "process_birth", lambda pid: None)
    monkeypatch.setattr(controller.time, "sleep", lambda seconds: None)
    return SimpleNamespace(root=root, plan=plan, rows=rows, manifest=manifest)


def launch_record(setup, job, *, pid=12345, birth="original", gpu=0):
    attempt = setup.root / "queue/jobs" / job["key"] / "attempt001"
    controller.publish(
        attempt / "launch/record.json",
        {
            "protocol_id": setup.plan["id"],
            "job": job,
            "pid": pid,
            "birth": birth,
            "gpu": gpu,
        },
    )
    return attempt


def test_fixed_budget_and_fresh_seed_dependency_matrix(tmp_path):
    jobs = controller.make_jobs(tmp_path)
    assert len(jobs) == 24
    assert len({j["key"] for j in jobs}) == 24
    assert [j["kind"] for j in jobs[:6]] == ["test", "prefix"] * 3
    assert {j["branch"] for j in jobs[:6]} == {
        "c_only_test_extension",
        "training_replication",
    }
    assert controller.budgets() == dict(
        old_c_only_test_sessions=3441,
        fresh_prefix_steps=894,
        branch_training_steps=10728,
        replication_physical_training_steps=11622,
        replication_final_models=9,
        replication_outer_updates=24,
        replication_feedback_sessions=16800,
        replication_test_sessions=10323,
        new_local_sessions=30564,
        maximum_generate_calls=978048,
        new_Probe_or_QA_sessions=0,
        external_API_calls=0,
    )
    completed = {"replication-prefix-seed137"}
    active = {j["key"] for j in jobs[:6]}
    ready = controller.ready_jobs(jobs, completed, active)
    assert [j["key"] for j in ready] == [
        f"replication-train-seed137-{arm}" for arm in controller.ARMS
    ]
    # A scientific result is not a prerequisite of any new training branch.
    assert all(not any("extension" in key for key in j["dependencies"]) for j in jobs[6:])
    completed.add("replication-train-seed137-full")
    ready = controller.ready_jobs(jobs, completed, active)
    assert any(j["key"] == "replication-test-seed137-full" for j in ready)
    assert not any(j["key"] == "replication-test-seed251-full" for j in ready)


def test_memory_floor_uses_each_job_and_does_not_starve_eligible_evaluation(tmp_path):
    jobs = controller.make_jobs(tmp_path)
    active = {j["key"] for j in jobs if j["kind"] == "prefix"}
    ready = controller.admitted_jobs(jobs, set(), active, {"free_mib": 24576})
    assert len(ready) == 3
    assert all(j["branch"] == "c_only_test_extension" for j in ready)
    assert controller.admitted_jobs(jobs, set(), set(), {"free_mib": 24575}) == []
    completed = {"replication-prefix-seed137", "replication-train-seed137-static"}
    active |= {j["key"] for j in jobs if j["branch"] == "c_only_test_extension"}
    ready = controller.admitted_jobs(jobs, completed, active, {"free_mib": 32768})
    assert [j["key"] for j in ready] == ["replication-test-seed137-static"]
    ready = controller.admitted_jobs(jobs, completed, active, {"free_mib": 49152})
    assert [j["key"] for j in ready] == [
        "replication-train-seed137-c_only",
        "replication-train-seed137-full",
        "replication-test-seed137-static",
    ]


@pytest.mark.parametrize("bad", ["root", "mutable_controller", "source_bytes", "registration"])
def test_fixed_root_frozen_source_and_registration_identity(setup_controller, monkeypatch, bad):
    setup = setup_controller
    target = setup.root
    if bad == "root":
        target = setup.root.parent / "other"
    elif bad == "mutable_controller":
        monkeypatch.setattr(controller, "__file__", str(SCRIPT))
    elif bad == "source_bytes":
        (setup.root / "implementation" / controller.FILES[1]).write_bytes(b"changed")
    else:
        path = Path(setup.plan["extension_registration"]["path"])
        path.write_text('{"id":"not-the-bound-registration"}')
    with pytest.raises(ValueError):
        controller.Controller(target)


def test_launch_has_single_attempt_and_no_scientific_runtime_mutation(
    setup_controller, monkeypatch
):
    setup = setup_controller
    instance = controller.Controller(setup.root)
    calls = []

    def fake_popen(command, **kwargs):
        calls.append((command, kwargs))
        return SimpleNamespace(pid=24680, poll=lambda: None)

    monkeypatch.setattr(controller.subprocess, "Popen", fake_popen)
    monkeypatch.setattr(controller, "process_birth", lambda pid: "fixed-birth")
    job = instance.jobs[0]
    instance.launch(job, setup.rows[0])
    assert len(calls) == 1
    command, kwargs = calls[0]
    assert "--resume" not in command
    assert kwargs["cwd"] == controller.FROZEN
    assert kwargs["env"]["PYTHONPATH"] == str(controller.FROZEN / "trusted_data_synthesis/src")
    assert "CUDA_VISIBLE_DEVICES" not in kwargs["env"]
    assert kwargs["start_new_session"] is True
    with pytest.raises(ValueError, match="repeated"):
        instance.launch(job, setup.rows[1])
    instance.children.clear()
    with pytest.raises(ValueError, match="attempt"):
        instance.launch(job, setup.rows[1])
    assert len(calls) == 1


def test_worker_cap_and_gpu_mapping_rejected_before_launch(setup_controller):
    setup = setup_controller
    instance = controller.Controller(setup.root)
    instance.children = {f"CPU-{i}": {"gpu": i} for i in range(8)}
    with pytest.raises(ValueError, match="eight-GPU"):
        instance.launch(instance.jobs[0], setup.rows[0])
    instance.children.clear()
    with pytest.raises(ValueError, match="GPU mapping"):
        instance.launch(instance.jobs[0], {**setup.rows[0], "uuid": "different"})


@pytest.mark.parametrize(
    "rc,result_exists,expected_complete",
    [(0, True, True), (0, False, False), (7, True, False), (7, False, False)],
)
def test_reap_saves_exit_and_missing_result_without_retry(
    setup_controller, rc, result_exists, expected_complete
):
    setup = setup_controller
    instance = controller.Controller(setup.root)
    job = instance.jobs[0]
    if result_exists:
        controller.publish(Path(job["result"]), {"CPU_fixture": True})
    attempt = setup.root / "queue/jobs" / job["key"] / "attempt001"
    instance.children[job["key"]] = dict(
        job=job,
        attempt=attempt,
        process=SimpleNamespace(poll=lambda: rc),
        pid=12345,
        birth="b",
        gpu=0,
    )
    instance.reap()
    assert not instance.children
    ended = controller.checked(attempt / "exit/record.json")
    assert ended["exit_code"] == rc
    assert ended["completed"] is expected_complete
    assert ended["no_automatic_retry"] is True
    assert (job["key"] in instance.completed) is expected_complete
    assert bool(instance.failures) is not expected_complete


def test_cold_resume_pid_birth_prevents_reused_pid_adoption(setup_controller, monkeypatch):
    setup = setup_controller
    job = setup.plan["jobs"][0]
    launch_record(setup, job)
    with pytest.raises(ValueError, match="explicit resume"):
        controller.Controller(setup.root)
    monkeypatch.setattr(controller, "process_birth", lambda pid: "different-birth")
    instance = controller.Controller(setup.root, resume=True)
    assert instance.failures and not instance.children and not instance.completed
    monkeypatch.setattr(controller, "process_birth", lambda pid: "original")
    instance = controller.Controller(setup.root, resume=True)
    assert set(instance.children) == {job["key"]}
    assert instance.children[job["key"]]["process"] is None


def test_unowned_existing_complete_result_never_generates_again(setup_controller):
    setup = setup_controller
    controller.publish(Path(setup.plan["jobs"][0]["result"]), {"CPU_fixture": True})
    with pytest.raises(ValueError, match="unowned"):
        controller.Controller(setup.root, resume=True)


def test_partial_freeze_rejected_without_overwriting_source(tmp_path, monkeypatch):
    root = tmp_path / "partial"
    target = root / "implementation"
    target.mkdir(parents=True)
    first = target / controller.FILES[0]
    first.write_bytes(b"partial-existing-source")
    monkeypatch.setattr(controller.subprocess, "check_output", lambda *args, **kwargs: b"committed")
    with pytest.raises(ValueError, match="partial implementation freeze"):
        controller.freeze(root, "a" * 40)
    assert first.read_bytes() == b"partial-existing-source"
    assert not (target / "record.json").exists()


def test_controller_failure_stops_dispatch_and_drains_owned_children(setup_controller, monkeypatch):
    setup = setup_controller
    instance = controller.Controller(setup.root)
    job = instance.jobs[0]
    attempt = setup.root / "queue/jobs" / job["key"] / "attempt001"
    polls = iter([None, 0])
    instance.children[job["key"]] = dict(
        job=job,
        attempt=attempt,
        pid=12345,
        birth="b",
        gpu=0,
        process=SimpleNamespace(poll=lambda: next(polls)),
    )
    phases = []
    monkeypatch.setattr(instance, "status", phases.append)
    monkeypatch.setattr(instance, "launch", forbid)

    def unavailable_inventory():
        raise RuntimeError("CPU mock inventory failure")

    monkeypatch.setattr(controller, "inventory", unavailable_inventory)
    instance.run()
    assert instance.failures
    assert not instance.children
    assert phases[-1] == "BLOCKED_SAVED"
    assert (attempt / "exit/record.json").exists()


def test_intent_only_cold_resume_blocks_without_replacement(setup_controller):
    setup = setup_controller
    job = setup.plan["jobs"][0]
    attempt = setup.root / "queue/jobs" / job["key"] / "attempt001"
    controller.publish(attempt / "intent/record.json", {"protocol_id": setup.plan["id"]})
    with pytest.raises(ValueError, match="partial prior attempt"):
        controller.Controller(setup.root)
    instance = controller.Controller(setup.root, resume=True)
    assert instance.failures and not instance.children
    instance.run()
    assert not (attempt / "launch/record.json").exists()


@pytest.mark.parametrize("problem", ["foreign_exit", "replaced_result"])
def test_resume_rejects_foreign_exit_or_replaced_result(setup_controller, problem):
    setup = setup_controller
    job = setup.plan["jobs"][0]
    attempt = launch_record(setup, job)
    controller.publish(Path(job["result"]), {"CPU_fixture": True})
    result = controller.entry(job["result"])
    if problem == "replaced_result":
        result["sha256"] = "other-original-result"
    controller.publish(
        attempt / "exit/record.json",
        {
            "protocol_id": "foreign" if problem == "foreign_exit" else setup.plan["id"],
            "key": job["key"],
            "completed": True,
            "result": result,
        },
    )
    with pytest.raises(ValueError, match="foreign worker exit|changed or replaced"):
        controller.Controller(setup.root, resume=True)


def test_early_worker_exit_without_birth_is_owned_and_reaped(setup_controller, monkeypatch):
    setup = setup_controller
    instance = controller.Controller(setup.root)
    job = instance.jobs[0]
    monkeypatch.setattr(
        controller.subprocess,
        "Popen",
        lambda *a, **k: SimpleNamespace(
            pid=24680,
            poll=lambda: 19,
        ),
    )
    instance.launch(job, setup.rows[0])
    assert instance.children[job["key"]]["birth"] is None
    instance.reap()
    assert not instance.children and instance.failures
    ended = controller.checked(
        setup.root / "queue/jobs" / job["key"] / "attempt001/exit/record.json"
    )
    assert ended["exit_code"] == 19 and ended["completed"] is False


def test_committed_freeze_cannot_rebind_revision(setup_controller, monkeypatch):
    monkeypatch.setattr(controller.subprocess, "check_output", lambda *args, **kwargs: b"fixture")
    with pytest.raises(ValueError, match="cannot rebind"):
        controller.freeze(setup_controller.root, "b" * 40)


def test_partial_cpu_registration_cannot_publish_gpu_protocol(tmp_path, monkeypatch):
    source = tmp_path / "V18"
    parent = source / "completed_v23"
    root = source / "v25_training_replication_01"
    completed = controller.publish(parent / "result/record.json", {"shrink_status": "complete"})
    audit = tmp_path / "audit.txt"
    audit.write_text("CPU test authority fixture")
    monkeypatch.setattr(controller, "ROOT", root)
    monkeypatch.setattr(controller, "V18", source)
    monkeypatch.setattr(controller, "PARENT", parent)
    monkeypatch.setattr(controller, "PARENT_ID", completed["id"])
    monkeypatch.setattr(controller, "cleanup_receipt", lambda: {"sha256": "CPU-cleanup"})
    monkeypatch.setattr(controller, "disk_available", lambda root: 800 * 1024**3)
    monkeypatch.setattr(controller, "freeze", lambda *args: {"id": "frozen-fixture"})
    monkeypatch.setattr(controller, "inventory", forbid)
    calls = []

    def partial_cpu(root, script, args):
        calls.append((script, args))
        if args[0] == "prepare":
            controller.publish(
                root / "training_replication/registration/record.json", {"CPU": True}
            )
            return
        raise ValueError("CPU mock partial registration")

    monkeypatch.setattr(controller, "cpu_command", partial_cpu)
    with pytest.raises(ValueError, match="partial registration"):
        controller.initialize(root, "a" * 40, audit)
    assert len(calls) == 2
    assert not (root / "protocol/record.json").exists()


def test_completed_successor_cannot_reopen(setup_controller):
    setup = setup_controller
    controller.publish(setup.root / "result/record.json", {"completed": True})
    with pytest.raises(ValueError, match="completed queue"):
        controller.Controller(setup.root, resume=True)


@pytest.mark.parametrize("kind,free", [("test", 24575), ("prefix", 32767), ("arm", 49151)])
def test_direct_launch_checks_per_job_floor_before_popen(setup_controller, kind, free):
    setup = setup_controller
    instance = controller.Controller(setup.root)
    job = next(j for j in instance.jobs if j["kind"] == kind)
    with pytest.raises(ValueError, match="memory admission"):
        instance.launch(job, {**setup.rows[0], "free_mib": free})


def test_no_double_owned_gpu_and_disk_floor(setup_controller, monkeypatch):
    instance = controller.Controller(setup_controller.root)
    instance.children = {"other": {"gpu": 0}}
    with pytest.raises(ValueError, match="one owned worker"):
        instance.launch(instance.jobs[0], setup_controller.rows[0])
    instance.children.clear()
    monkeypatch.setattr(controller, "disk_available", lambda root: 0)
    with pytest.raises(ValueError, match="disk admission"):
        instance.launch(instance.jobs[0], setup_controller.rows[0])


def test_block_scoring_waits_all_own_models_and_ignores_effects(setup_controller, monkeypatch):
    instance = controller.Controller(setup_controller.root)
    calls = []
    monkeypatch.setattr(controller, "cpu_command", lambda *a: calls.append(a))
    extension = [j["key"] for j in instance.jobs if j["branch"] == "c_only_test_extension"]
    replication = [j["key"] for j in instance.jobs if j["branch"] == "replication_evaluation"]
    instance.completed = set(extension[:-1])
    instance.score_ready_blocks()
    assert calls == []
    instance.completed.add(extension[-1])
    instance.score_ready_blocks()
    assert len(calls) == 1 and calls[0][2][-1].endswith("c_only_test_extension")
    # A may have any scientific effect; readiness depends only on fixed completion.
    controller.publish(
        instance.root / "c_only_test_extension/summary/record.json", {"effect": -1.0}
    )
    instance.completed.update(replication[:-1])
    instance.score_ready_blocks()
    assert len(calls) == 1
    instance.completed.add(replication[-1])
    instance.score_ready_blocks()
    assert len(calls) == 2 and calls[-1][2][-1].endswith("replication_evaluation")


@pytest.mark.parametrize("change", ["status", "count", "protection"])
def test_cleanup_completion_and_protection_gate(tmp_path, monkeypatch, change):
    import json

    path = tmp_path / "cleanup.json"
    data = {"status": "COMPLETE", "deleted_count": 17760, "protected_after": {"unchanged": True}}
    if change == "status":
        data["status"] = "PARTIAL_FAILURE"
    elif change == "count":
        data["deleted_count"] = 0
    else:
        data["protected_after"]["unchanged"] = False
    path.write_text(json.dumps(data))
    monkeypatch.setattr(controller, "CLEANUP", path)
    with pytest.raises(ValueError, match="cleanup must complete"):
        controller.cleanup_receipt()
    path.write_text(
        json.dumps(
            {
                "status": "COMPLETE",
                "deleted_count": 17760,
                "protected_after": {"unchanged": True},
            }
        )
    )
    assert controller.cleanup_receipt()["sha256"] == hashlib.sha256(path.read_bytes()).hexdigest()


def test_disk_and_parent_gate_precede_freeze(tmp_path, monkeypatch):
    source = tmp_path / "V18"
    parent = source / "completed_v23"
    root = source / "v25_training_replication_01"
    completed = controller.publish(parent / "result/record.json", {"shrink_status": "complete"})
    monkeypatch.setattr(controller, "ROOT", root)
    monkeypatch.setattr(controller, "V18", source)
    monkeypatch.setattr(controller, "PARENT", parent)
    monkeypatch.setattr(controller, "PARENT_ID", completed["id"])
    monkeypatch.setattr(controller, "cleanup_receipt", lambda: {})
    monkeypatch.setattr(controller, "disk_available", lambda root: 399 * 1024**3)
    monkeypatch.setattr(controller, "freeze", forbid)
    with pytest.raises(ValueError, match="400 GiB"):
        controller.initialize(root, "a" * 40, tmp_path / "unused-audit")
