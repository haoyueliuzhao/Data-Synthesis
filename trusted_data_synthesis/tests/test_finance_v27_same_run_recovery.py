"""CPU-only recovery/adoption fault tests; no GPU, API or real process signals."""

import importlib.util
import json
from pathlib import Path
from types import SimpleNamespace

import pytest

SCRIPTS = Path(__file__).resolve().parents[1] / "scripts"


def module(name):
    spec = importlib.util.spec_from_file_location(name + "_test_fixture", SCRIPTS / (name + ".py"))
    loaded = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(loaded)
    return loaded


c = module("finqa_v27_same_run_recovery")
base = module("finqa_v26_execution_continuation")
old = module("finqa_v25_replication_controller")


def forbid(*args, **kwargs):
    raise AssertionError("CPU fixture cannot launch real workers or inspect a real GPU")


def replace_record(path, value):
    value = {k: v for k, v in value.items() if k != "id"}
    value["id"] = c.digest(value)
    Path(path).write_text(json.dumps(value))
    return value


@pytest.fixture
def setup(tmp_path, monkeypatch):
    source = tmp_path / "v25"
    predecessor = source / "execution_continuation_01"
    root = source / "same_run_recovery_01"
    root.mkdir(parents=True)
    rows = [dict(index=i, uuid=f"GPU-CPU-{i}", free_mib=0, cpu_affinity="0-3") for i in range(8)]
    rows[3]["free_mib"], rows[7]["free_mib"] = 31000, 81154
    science = c.publish(
        source / "protocol/record.json",
        dict(
            jobs=old.make_jobs(source),
            budgets=old.budgets(),
            memory_floors_mib=old.MEMORY_FLOORS,
            dispatch_disk_floor_bytes=32 * 1024**3,
            gpu_uuids={str(r["index"]): r["uuid"] for r in rows},
            cpu_affinity={str(r["index"]): r["cpu_affinity"] for r in rows},
        ),
    )
    c.publish(source / "implementation/record.json", dict(scientific="frozen fixture"))
    predecessor_plan = c.publish(
        predecessor / "protocol/record.json",
        dict(
            origins={
                j["key"]: dict(state="never_dispatched", origin_attempt=None)
                for j in science["jobs"]
            }
        ),
    )
    c.publish(predecessor / "implementation/record.json", dict(execution="frozen fixture"))
    (predecessor / "queue").mkdir()
    (predecessor / "queue/status.json").write_text(json.dumps(dict(phase="DRAINING_AFTER_FAILURE")))
    c.publish(root / "handoff/record.json", dict(controller_only=True))
    hashes = {}
    for name in c.FILES:
        path = root / "implementation" / name
        path.parent.mkdir(exist_ok=True)
        path.write_text("# CPU fixture only\n")
        hashes[name] = c.file_entry(path)["sha256"]
    manifest = c.publish(
        root / "implementation/record.json", dict(source_commit="a" * 40, sha256=hashes)
    )
    proof = dict(eligible=True, job_key=c.RESUME_KEY, id="stable-CPU-fixture")
    origins = {
        j["key"]: dict(state="never_dispatched", origin_attempt=None) for j in science["jobs"]
    }
    completed = {
        "extension-test-seed11-c_only",
        "extension-test-seed29-c_only",
        "replication-prefix-seed137",
        "replication-prefix-seed251",
        "replication-prefix-seed389",
    }
    for job in science["jobs"]:
        if job["key"] in completed:
            c.publish(job["result"], dict(fixture_result=job["key"]))
            origins[job["key"]] = dict(
                state="completed_adopted", result=c.entry(job["result"]), origin_attempt=None
            )
    origins[c.RESUME_KEY] = dict(
        state="explicit_same_run_checkpoint_resume",
        proof=proof,
        origin_attempt=str(predecessor / "queue/jobs" / c.RESUME_KEY / "attempt001"),
    )
    plan = c.publish(
        root / "protocol/record.json",
        dict(
            implementation_id=manifest["id"],
            scientific_protocol=c.entry(source / "protocol/record.json"),
            scientific_implementation=c.entry(source / "implementation/record.json"),
            predecessor_protocol=c.entry(predecessor / "protocol/record.json"),
            predecessor_implementation=c.entry(predecessor / "implementation/record.json"),
            predecessor_terminal_status=c.file_entry(predecessor / "queue/status.json"),
            handoff=c.entry(root / "handoff/record.json"),
            jobs=science["jobs"],
            budgets=science["budgets"],
            scientific_memory_floors_mib=science["memory_floors_mib"],
            execution_memory_floors_mib=c.EXECUTION_FLOORS,
            stable_observations=c.STABLE_OBSERVATIONS,
            poll_seconds=c.POLL_SECONDS,
            maximum_explicit_checkpoint_resume_launches={c.RESUME_KEY: 1},
            origins=origins,
        ),
    )
    legacy = SimpleNamespace(
        inventory=lambda: rows,
        process_birth=lambda pid: "123456",
        disk_available=lambda root: 600 * 1024**3,
        atomic_status=old.atomic_status,
        command_environment=lambda: {"FIXTURE_ONLY": "1"},
        PYTHON=Path("/cpu-fixture/python"),
        FROZEN=Path("/cpu-fixture/runtime"),
        cpu_command=forbid,
    )
    admission = SimpleNamespace(prove_clean_precompute_rejection=lambda *args: dict(clean=True))
    recovery = SimpleNamespace(prove_same_run_gradient_oom_resume=lambda *args: dict(proof))
    monkeypatch.setattr(c, "SOURCE_ROOT", source)
    monkeypatch.setattr(c, "PREDECESSOR", predecessor)
    monkeypatch.setattr(c, "ROOT", root)
    monkeypatch.setattr(c, "__file__", str(root / "implementation" / c.FILES[0]))
    monkeypatch.setattr(c, "verify_handoff", lambda *args: {})
    monkeypatch.setattr(
        c,
        "load_module",
        lambda path, name: recovery if Path(path).name == c.FILES[1] else admission,
    )
    monkeypatch.setattr(base, "SOURCE_ROOT", source)
    monkeypatch.setattr(base, "verify_source", lambda: (science, legacy))
    monkeypatch.setattr(c.subprocess, "Popen", forbid)
    monkeypatch.setattr(c.time, "sleep", forbid)
    return SimpleNamespace(
        source=source,
        predecessor=predecessor,
        root=root,
        plan=plan,
        predecessor_plan=predecessor_plan,
        science=science,
        legacy=legacy,
        recovery=recovery,
        admission=admission,
        proof=proof,
        rows=rows,
        monkeypatch=monkeypatch,
        controller=c.controller_type(base),
    )


def instance(setup, resume=False):
    return setup.controller(setup.root, resume=resume)


def job_for(setup, key):
    return next(j for j in setup.science["jobs"] if j["key"] == key)


def live_origin(setup, key="extension-test-seed47-c_only", *, birth="123456"):
    job = job_for(setup, key)
    attempt = setup.predecessor / "queue/jobs" / key / "attempt001"
    started = c.publish(
        attempt / "launch/record.json",
        dict(
            protocol_id=setup.predecessor_plan["id"],
            scientific_protocol_id=setup.science["id"],
            job=job,
            pid=77777,
            birth=birth,
            gpu=3,
            command=["original immutable worker command"],
        ),
    )
    origin = dict(
        state="live_predecessor_adopted",
        pid=started["pid"],
        birth=started["birth"],
        gpu=3,
        command=started["command"],
        origin_attempt=str(attempt),
        origin_launch=c.entry(attempt / "launch/record.json"),
    )
    setup.plan["origins"][key] = origin
    setup.plan = replace_record(setup.root / "protocol/record.json", setup.plan)
    return job, origin


def test_execution_floor_stronger_without_altering_scientific_matrix(setup):
    original = json.loads(json.dumps(setup.science["jobs"]))
    assert c.execution_floor(job_for(setup, c.RESUME_KEY)) == 76800
    assert c.execution_floor(job_for(setup, "replication-train-seed251-full")) == 76800
    assert c.execution_floor(job_for(setup, "replication-train-seed137-static")) == 49152
    assert c.execution_floor(job_for(setup, "extension-test-seed47-c_only")) == 24576
    assert setup.science["jobs"] == original
    assert job_for(setup, c.RESUME_KEY)["minimum_free_mib"] == 49152


def test_live_adoption_creates_shadow_receipts_without_popen_or_old_writes(setup):
    job, origin = live_origin(setup)
    original = c.entry(Path(origin["origin_attempt"]) / "launch/record.json")
    controller = instance(setup)
    child = controller.children[job["key"]]
    assert child["process"] is None and child["pid"] == 77777 and child["birth"] == "123456"
    receipt = c.checked(child["attempt"] / "launch/record.json")
    assert receipt["adopted_existing_process"] is True and receipt["new_process_started"] is False
    assert receipt["origin_launch"] == original
    assert c.entry(Path(origin["origin_attempt"]) / "launch/record.json") == original
    assert not (Path(origin["origin_attempt"]) / "exit/record.json").exists()


def test_adopted_worker_completion_only_writes_successor_exit(setup):
    job, origin = live_origin(setup)
    controller = instance(setup)
    c.publish(job["result"], dict(actual="completed fixture"))
    setup.legacy.process_birth = lambda pid: None
    controller.reap()
    assert job["key"] in controller.completed and not controller.children
    assert not (Path(origin["origin_attempt"]) / "exit/record.json").exists()
    receipt = c.checked(setup.root / "queue/jobs" / job["key"] / "attempt001/exit/record.json")
    assert receipt["completed"] is True and receipt["no_feedback_resampling"] is True
    assert "no_scientific_retry" not in receipt


def test_worker_completing_between_registration_and_adoption_is_adopted(setup):
    job, _ = live_origin(setup)
    c.publish(job["result"], dict(completed_during_handoff=True))
    setup.legacy.process_birth = lambda pid: None
    controller = instance(setup)
    assert (
        job["key"] in controller.completed and not controller.children and not controller.failures
    )


def test_dead_adopted_worker_without_result_blocks_without_restarting(setup):
    live_origin(setup)
    setup.legacy.process_birth = lambda pid: None
    controller = instance(setup)
    assert not controller.children and len(controller.failures) == 1
    assert "no further" in controller.failures[0]["reason"]


def test_resume_checkpoint_exactly_once_same_worker_cli_and_truthful_receipts(setup):
    controller = instance(setup)
    calls = []
    setup.monkeypatch.setattr(
        c.subprocess,
        "Popen",
        lambda command, **kw: (
            calls.append((command, kw)) or SimpleNamespace(pid=88888, poll=lambda: None)
        ),
    )
    job = job_for(setup, c.RESUME_KEY)
    assert controller.launch(job, setup.rows[7])
    command, kwargs = calls[0]
    assert command[-1] == "--resume"
    assert str(setup.source / "implementation/finqa_v25_training_replication.py") in command
    assert command[command.index("--root") + 1] == str(setup.source / "training_replication")
    assert kwargs["start_new_session"] is True
    receipt = c.checked(controller.children[c.RESUME_KEY]["attempt"] / "intent/record.json")
    assert receipt["job"] == job and receipt["job"]["minimum_free_mib"] == 49152
    assert receipt["execution_minimum_free_mib"] == 76800
    assert receipt["same_run_resume_authorization"] == setup.proof
    assert receipt["uncommitted_gradient_recomputation"] is True
    assert receipt["no_feedback_resampling"] is True and "no_scientific_retry" not in receipt
    controller.children.clear()
    with pytest.raises(ValueError, match="single explicit"):
        controller.launch(job, setup.rows[7])
    assert len(calls) == 1


def test_resume_proof_changes_block_before_any_new_intent(setup):
    controller = instance(setup)
    setup.recovery.prove_same_run_gradient_oom_resume = lambda *args: dict(
        setup.proof, id="changed"
    )
    with pytest.raises(ValueError, match="proof changed"):
        controller.launch(job_for(setup, c.RESUME_KEY), setup.rows[7])
    assert not (setup.root / "queue/jobs").exists()


def test_gpu_recheck_after_cpu_resume_proof_does_not_relax_to_old_floor(setup):
    controller = instance(setup)

    def proof(*args):
        setup.rows[7]["free_mib"] = 60000
        return dict(setup.proof)

    setup.recovery.prove_same_run_gradient_oom_resume = proof
    assert controller.launch(job_for(setup, c.RESUME_KEY), setup.rows[7]) is False
    assert not (setup.root / "queue/jobs").exists() and not controller.failures


def test_fresh_job_uses_no_resume_flag(setup):
    controller = instance(setup)
    calls = []
    setup.monkeypatch.setattr(
        c.subprocess,
        "Popen",
        lambda command, **kw: (
            calls.append(command) or SimpleNamespace(pid=88888, poll=lambda: None)
        ),
    )
    assert controller.launch(job_for(setup, "extension-test-seed47-c_only"), setup.rows[3])
    assert "--resume" not in calls[0]


def test_resume_failure_stops_and_never_attempts_clean_precompute_proof(setup):
    controller = instance(setup)
    setup.admission.prove_clean_precompute_rejection = forbid
    setup.monkeypatch.setattr(
        c.subprocess, "Popen", lambda *args, **kw: SimpleNamespace(pid=88888, poll=lambda: 1)
    )
    assert controller.launch(job_for(setup, c.RESUME_KEY), setup.rows[7])
    controller.reap()
    assert len(controller.failures) == 1 and not controller.children
    assert not (setup.root / "queue/jobs" / c.RESUME_KEY / "attempt001/defer").exists()


def test_new_fresh_clean_admission_refusal_can_still_defer(setup):
    controller = instance(setup)
    setup.monkeypatch.setattr(
        c.subprocess, "Popen", lambda *args, **kw: SimpleNamespace(pid=88888, poll=lambda: 1)
    )
    job = job_for(setup, "extension-test-seed47-c_only")
    assert controller.launch(job, setup.rows[3])
    controller.reap()
    assert not controller.failures and controller.rejections[job["key"]] == 1


def test_stricter_floor_and_two_observation_policy_in_dispatch(setup):
    controller = instance(setup)
    controller.jobs = [job_for(setup, c.RESUME_KEY)]
    launches = []
    setup.monkeypatch.setattr(controller, "launch", lambda job, row: launches.append(row["index"]))
    setup.rows[7]["free_mib"] = 76799
    controller.dispatch()
    controller.dispatch()
    assert launches == []
    setup.rows[7]["free_mib"] = 76800
    controller.dispatch()
    assert launches == []
    controller.dispatch()
    assert launches == [7]
    assert controller.jobs[0]["minimum_free_mib"] == 49152


def test_resume_controller_adopts_existing_recovery_process_without_second_launch(setup):
    controller = instance(setup)
    setup.monkeypatch.setattr(
        c.subprocess, "Popen", lambda *args, **kw: SimpleNamespace(pid=88888, poll=lambda: None)
    )
    controller.launch(job_for(setup, c.RESUME_KEY), setup.rows[7])
    setup.monkeypatch.setattr(c.subprocess, "Popen", forbid)
    with pytest.raises(ValueError, match="explicit resume"):
        instance(setup)
    resumed = instance(setup, resume=True)
    assert resumed.children[c.RESUME_KEY]["pid"] == 88888
    assert resumed.children[c.RESUME_KEY]["process"] is None


def test_partial_adoption_resume_reconstructs_only_missing_shadow_launch(setup):
    job, origin = live_origin(setup)
    publish = c.publish

    def broken(path, value):
        if Path(path).parent.name == "launch":
            raise OSError("fixture receipt error")
        return publish(path, value)

    setup.monkeypatch.setattr(c, "publish", broken)
    with pytest.raises(OSError):
        instance(setup)
    setup.monkeypatch.setattr(c, "publish", publish)
    resumed = instance(setup, resume=True)
    assert resumed.children[job["key"]]["pid"] == origin["pid"]


@pytest.mark.parametrize(
    "change", ["wrong_root", "mutable_controller", "old_status", "new_code", "floor"]
)
def test_frozen_recovery_boundaries(setup, change):
    root = setup.root
    if change == "wrong_root":
        root = root.parent / "other"
    elif change == "mutable_controller":
        setup.monkeypatch.setattr(c, "__file__", str(SCRIPTS / c.FILES[0]))
    elif change == "old_status":
        (setup.predecessor / "queue/status.json").write_text("{}")
    elif change == "new_code":
        (root / "implementation" / c.FILES[0]).write_text("changed")
    else:
        setup.plan["execution_memory_floors_mib"] = dict(c.EXECUTION_FLOORS, automatic=49152)
        replace_record(root / "protocol/record.json", setup.plan)
    with pytest.raises(ValueError):
        setup.controller(root)


def test_status_reports_recomputation_not_zero_compute_retry(setup):
    controller = instance(setup)
    old_status = c.file_entry(setup.predecessor / "queue/status.json")
    controller.status("WAITING_FOR_RESOURCES")
    status = json.loads((setup.root / "queue/status.json").read_text())
    assert status["uncommitted_gradient_recomputation"] is True
    assert status["no_feedback_resampling"] is True and "no_scientific_retry" not in status
    assert c.file_entry(setup.predecessor / "queue/status.json") == old_status


def test_failure_drains_existing_adopted_workers_without_signals(setup):
    job, _ = live_origin(setup)
    controller = instance(setup)
    controller.failures.append(dict(reason="resume failed"))
    phases = []
    setup.monkeypatch.setattr(controller, "status", lambda phase: phases.append(phase))

    def advance(_):
        c.publish(job["result"], dict(completed=True))
        setup.legacy.process_birth = lambda pid: None

    setup.monkeypatch.setattr(c.time, "sleep", advance)
    controller.run()
    assert phases == ["DRAINING_AFTER_FAILURE", "DRAINING_AFTER_FAILURE", "BLOCKED_SAVED"]
    assert not controller.children


def test_reconciliation_accepts_detached_completion_and_exact_oom_only(setup):
    # Build the post-handoff disk state without instantiating any controller.
    predecessor = dict(setup.predecessor_plan)
    predecessor["origins"] = {key: dict(value) for key, value in setup.plan["origins"].items()}
    for key in (c.RESUME_KEY, "extension-test-seed47-c_only"):
        predecessor["origins"][key] = dict(state="never_dispatched", origin_attempt=None)
    predecessor = replace_record(setup.predecessor / "protocol/record.json", predecessor)
    setup.predecessor_plan = predecessor
    job, origin = live_origin(setup)
    c.publish(job["result"], dict(completed_during_handoff=True))
    resume_job = job_for(setup, c.RESUME_KEY)
    attempt = setup.predecessor / "queue/jobs" / c.RESUME_KEY / "attempt001"
    c.publish(
        attempt / "launch/record.json",
        dict(
            protocol_id=predecessor["id"],
            scientific_protocol_id=setup.science["id"],
            job=resume_job,
            pid=88888,
            birth="123456",
            gpu=7,
            command=["fixture-only"],
        ),
    )
    c.publish(
        attempt / "exit/record.json",
        dict(protocol_id=predecessor["id"], key=c.RESUME_KEY, completed=False, result=None),
    )
    setup.legacy.process_birth = lambda pid: None
    handoff = dict(known_worker_launches=[origin["origin_launch"]])
    origins = c.origins_from_predecessor(setup.science, setup.legacy, handoff, setup.proof)
    assert sum(value["state"] == "completed_adopted" for value in origins.values()) == 6
    assert origins[job["key"]]["detached_completed_during_handoff"] is True
    assert origins[c.RESUME_KEY]["state"] == "explicit_same_run_checkpoint_resume"
    assert sum(value["state"] == "never_dispatched" for value in origins.values()) == 17
