"""Small CPU-only fault tests; never load scientific workers, CUDA or test data."""

import hashlib
import importlib.util
from pathlib import Path
from types import SimpleNamespace

import pytest

SCRIPT = Path(__file__).resolve().parents[1] / "scripts/finqa_v23_followup_controller.py"
SPEC = importlib.util.spec_from_file_location("v23_followup_controller_tests", SCRIPT)
controller = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(controller)


def forbid(*args, **kwargs):
    raise AssertionError("CPU fixture must not invoke a real process, GPU or scientific module")


@pytest.fixture
def setup_controller(tmp_path, monkeypatch):
    root = tmp_path / "v23_confirmation_shrink_01"
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
    for branch in ("test_confirmation", "shrink_control"):
        path = root / branch / "registration/record.json"
        controller.publish(path, {"branch": branch, "applicable": True})
        refs[branch] = controller.entry(path)
    rows = [
        dict(index=i, uuid=f"CPU-GPU-{i}", free_mib=40000, cpu_affinity="0-3") for i in range(8)
    ]
    plan = controller.publish(
        root / "protocol/record.json",
        {
            "implementation_id": manifest["id"],
            "test_registration": refs["test_confirmation"],
            "shrink_registration": refs["shrink_control"],
            "api_model": "deepseek-flash",
            "API_calls_authorized": 0,
            "jobs": controller.make_jobs(root, True),
            "shrink_all_seeds_applicable": True,
            "gpu_uuids": {str(row["index"]): row["uuid"] for row in rows},
            "cpu_affinity": {str(row["index"]): row["cpu_affinity"] for row in rows},
        },
    )
    monkeypatch.setattr(controller, "ROOT", root)
    monkeypatch.setattr(controller, "__file__", str(implementation / controller.FILES[0]))
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


def test_fixed_job_matrix_and_per_seed_ready_dependency(tmp_path):
    jobs = controller.make_jobs(tmp_path, True)
    assert len(jobs) == 12
    assert len(controller.make_jobs(tmp_path, False)) == 6
    assert all(job["key"].startswith("test-") for job in jobs[:6])
    assert [job["key"] for job in jobs[6:9]] == [f"shrink-train-seed{s}" for s in (11, 29, 47)]
    completed = {"shrink-train-seed11"}
    active = {job["key"] for job in jobs[:6]} | {"shrink-train-seed29", "shrink-train-seed47"}
    ready = controller.ready_jobs(jobs, completed, active)
    assert [job["key"] for job in ready] == ["shrink-generate-seed11"]
    assert ready[0]["args"] == ["generate", "--seed", "11"]


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
        path = Path(setup.plan["test_registration"]["path"])
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


def test_partial_test_initialization_cannot_publish_gpu_protocol(tmp_path, monkeypatch):
    parent = tmp_path / "V18"
    root = parent / "v23_confirmation_shrink_01"
    completed = controller.publish(
        parent / "evaluation_continuation_01/queue/result/record.json",
        {
            "test1147_opened": False,
            "Experiment5_started": False,
        },
    )
    audit = tmp_path / "audit.txt"
    audit.write_text("CPU test authority fixture")
    monkeypatch.setattr(controller, "ROOT", root)
    monkeypatch.setattr(controller, "V18", parent)
    monkeypatch.setattr(controller, "PARENT_ID", completed["id"])
    monkeypatch.setattr(controller, "freeze", lambda *args: {"id": "frozen-fixture"})
    monkeypatch.setattr(controller, "inventory", forbid)

    def partial_register(test_root):
        controller.publish(
            test_root / "registration/record.json",
            {
                "jobs": {"seed11/static": {"model_identity": "CPU-fixture"}},
            },
        )

    test_module = SimpleNamespace(
        register=partial_register, generation_root=lambda path, job: path / "missing/run"
    )
    shrink_module = SimpleNamespace(
        prepare=lambda path, **kw: controller.publish(
            path / "registration/record.json",
            {"applicable": True},
        )
    )
    monkeypatch.setattr(
        controller,
        "load_module",
        lambda root, name: test_module if name == controller.FILES[1] else shrink_module,
    )
    with pytest.raises(ValueError, match="partial confirmation initialization"):
        controller.initialize(root, "a" * 40, audit)
    assert (root / "test_confirmation/registration/record.json").exists()
    assert not (root / "protocol/record.json").exists()
