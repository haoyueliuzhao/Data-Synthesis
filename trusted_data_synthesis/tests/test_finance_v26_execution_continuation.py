"""CPU-only continuation fault tests; no scientific worker, CUDA or API calls."""

import importlib.util
import json
from pathlib import Path
from types import SimpleNamespace

import pytest

SCRIPTS = Path(__file__).resolve().parents[1] / "scripts"


def module(name):
    spec = importlib.util.spec_from_file_location(name + "_tests", SCRIPTS / (name + ".py"))
    loaded = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(loaded)
    return loaded


c = module("finqa_v26_execution_continuation")
old = module("finqa_v25_replication_controller")


def forbid(*args, **kwargs):
    raise AssertionError("CPU fixture must not run a real GPU or scientific command")


@pytest.fixture
def setup(tmp_path, monkeypatch):
    source = tmp_path / "v25"
    root = source / "execution_continuation_01"
    root.mkdir(parents=True)
    rows = [
        dict(index=i, uuid=f"GPU-CPU-fixture-{i}", free_mib=0, cpu_affinity="0-3") for i in range(8)
    ]
    rows[3]["free_mib"], rows[7]["free_mib"] = 31000, 81154
    science = c.publish(
        source / "protocol/record.json",
        dict(
            jobs=old.make_jobs(source),
            budgets=old.budgets(),
            dispatch_disk_floor_bytes=32 * 1024**3,
            gpu_uuids={str(r["index"]): r["uuid"] for r in rows},
            cpu_affinity={str(r["index"]): r["cpu_affinity"] for r in rows},
        ),
    )
    c.publish(source / "implementation/record.json", dict(dummy="old scientific fixture"))
    (source / "queue").mkdir()
    (source / "queue/status.json").write_text(
        json.dumps(dict(phase="BLOCKED_SAVED", active_children=[]))
    )
    hashes = {}
    for name in c.FILES:
        path = root / "implementation" / name
        path.parent.mkdir(exist_ok=True)
        path.write_text("# CPU fixture only\n")
        hashes[name] = c.file_entry(path)["sha256"]
    manifest = c.publish(
        root / "implementation/record.json", dict(source_commit="a" * 40, sha256=hashes)
    )
    plan = c.publish(
        root / "protocol/record.json",
        dict(
            implementation_id=manifest["id"],
            scientific_protocol=c.entry(source / "protocol/record.json"),
            scientific_implementation=c.entry(source / "implementation/record.json"),
            legacy_terminal_status=c.file_entry(source / "queue/status.json"),
            jobs=science["jobs"],
            budgets=science["budgets"],
            memory_floors_mib=c.MEMORY_FLOORS,
            stable_observations=c.STABLE_OBSERVATIONS,
            poll_seconds=c.POLL_SECONDS,
            base_defer_seconds=c.BASE_DEFER_SECONDS,
            max_defer_seconds=c.MAX_DEFER_SECONDS,
            origins={
                j["key"]: dict(state="never_dispatched", origin_attempt=None)
                for j in science["jobs"]
            },
        ),
    )
    legacy = SimpleNamespace(
        inventory=lambda: rows,
        process_birth=lambda pid: "123456",
        disk_available=lambda root: 600 * 1024**3,
        atomic_status=old.atomic_status,
        command_environment=lambda: {"FIXTURE_ONLY": "1"},
        PYTHON=Path("/cpu-fixture/python"),
        FROZEN=Path("/cpu-fixture/scientific-runtime"),
        cpu_command=forbid,
    )
    proof = SimpleNamespace(
        prove_clean_precompute_rejection=lambda root, job, attempt: dict(clean=True, job=job["key"])
    )
    monkeypatch.setattr(c, "SOURCE_ROOT", source)
    monkeypatch.setattr(c, "ROOT", root)
    monkeypatch.setattr(c, "__file__", str(root / "implementation" / c.FILES[0]))
    monkeypatch.setattr(c, "verify_source", lambda: (science, legacy))
    monkeypatch.setattr(c, "load_module", lambda *args: proof)
    monkeypatch.setattr(c.subprocess, "Popen", forbid)
    monkeypatch.setattr(c.time, "sleep", forbid)
    return SimpleNamespace(
        root=root,
        source=source,
        science=science,
        plan=plan,
        legacy=legacy,
        proof=proof,
        rows=rows,
        monkeypatch=monkeypatch,
    )


def worker(setup, job, number=1, *, rc=None, birth="123456"):
    attempt = setup.root / "queue/jobs" / job["key"] / f"attempt{number:03d}"
    base = dict(
        protocol_id=setup.plan["id"],
        scientific_protocol_id=setup.science["id"],
        job=job,
        pid=77777,
        birth=birth,
        gpu=3,
        command=["CPU-fixture-only"],
    )
    c.publish(attempt / "intent/record.json", base)
    c.publish(attempt / "launch/record.json", base)
    (attempt / "worker.log").write_text("CPU fixture log\n")
    return dict(
        job=job,
        attempt=attempt,
        pid=77777,
        birth=birth,
        gpu=3,
        process=SimpleNamespace(poll=lambda: rc),
    )


def close(setup, child, *, complete=False, code=1):
    job = child["job"]
    c.publish(
        child["attempt"] / "exit/record.json",
        dict(
            protocol_id=setup.plan["id"],
            scientific_protocol_id=setup.science["id"],
            key=job["key"],
            completed=complete,
            exit_code=code,
            result=c.entry(job["result"]) if complete else None,
        ),
    )


def instance(setup):
    return c.Controller(setup.root)


def test_matrix_and_budgets_are_exactly_original(tmp_path):
    jobs = old.make_jobs(tmp_path)
    assert len(jobs) == 24
    assert c.MEMORY_FLOORS == old.MEMORY_FLOORS
    assert {
        int(j["args"][j["args"].index("--seed") + 1])
        for j in jobs
        if j["branch"] == "training_replication"
    } == {137, 251, 389}
    assert old.budgets()["replication_physical_training_steps"] == 11622
    assert old.budgets()["replication_test_sessions"] == 10323


def test_best_fit_keeps_original_ready_order_and_scarce_gpu(setup):
    done = {
        "extension-test-seed11-c_only",
        "extension-test-seed29-c_only",
        "replication-prefix-seed137",
    }
    pairs = c.assignments(setup.science["jobs"], done, set(), setup.rows)
    assert [(j["key"], r["index"]) for j, r in pairs] == [
        ("replication-prefix-seed251", 7),
        ("extension-test-seed47-c_only", 3),
    ]
    # Already-ready long arms must not jump ahead of the other fresh prefixes.
    assert not any(j["kind"] == "arm" for j, _ in pairs)


def test_best_fit_respects_dependencies_occupation_and_cooldown(setup):
    jobs = setup.science["jobs"]
    pairs = c.assignments(
        jobs, set(), {jobs[0]["key"]}, setup.rows, occupied={7}, deferred={jobs[2]["key"]}
    )
    assert [(j["key"], r["index"]) for j, r in pairs] == [("extension-test-seed47-c_only", 3)]
    assert c.assignments(jobs, set(), set(), [{"index": 0, "free_mib": 24575}]) == []


@pytest.mark.parametrize(
    "change", ["wrong_root", "mutable_controller", "source_bytes", "old_status"]
)
def test_frozen_bindings_and_old_queue_immutability(setup, change):
    root = setup.root
    if change == "wrong_root":
        root = root.parent / "other"
    elif change == "mutable_controller":
        setup.monkeypatch.setattr(c, "__file__", str(SCRIPTS / c.FILES[0]))
    elif change == "source_bytes":
        (root / "implementation" / c.FILES[0]).write_text("changed\n")
    else:
        (setup.source / "queue/status.json").write_text("{}")
    with pytest.raises(ValueError):
        c.Controller(root)


def test_launch_uses_original_worker_and_original_scientific_root(setup):
    controller = instance(setup)
    calls = []
    setup.monkeypatch.setattr(
        c.subprocess,
        "Popen",
        lambda command, **kw: (
            calls.append((command, kw)) or SimpleNamespace(pid=77777, poll=lambda: None)
        ),
    )
    job = controller.jobs[0]
    assert controller.launch(job, setup.rows[3])
    command, kwargs = calls[0]
    assert str(setup.source / "implementation" / job["script"]) in command
    assert command[command.index("--root") + 1] == str(setup.source / job["branch"])
    assert "--resume" not in command
    assert kwargs["start_new_session"] is True and kwargs["cwd"] == setup.legacy.FROZEN
    receipt = c.checked(setup.root / "queue/jobs" / job["key"] / "attempt001/launch/record.json")
    assert (
        receipt["scientific_protocol_id"] == setup.science["id"]
        and receipt["protocol_id"] == setup.plan["id"]
    )
    assert receipt["origin_attempt"] is None
    assert not (setup.source / "queue/jobs").exists()


def test_immediate_recheck_defers_before_creating_attempt(setup):
    controller = instance(setup)
    setup.legacy.inventory = lambda: [dict(r, free_mib=0) for r in setup.rows]
    assert controller.launch(controller.jobs[0], setup.rows[3]) is False
    assert not (setup.root / "queue/jobs").exists()
    assert not controller.failures


def test_stable_two_polls_then_dispatch(setup):
    controller = instance(setup)
    launches = []
    setup.monkeypatch.setattr(
        controller, "launch", lambda job, row: launches.append((job["key"], row["index"]))
    )
    controller.dispatch()
    assert launches == []
    controller.dispatch()
    assert launches == [("extension-test-seed11-c_only", 3), ("replication-prefix-seed137", 7)]


def test_failed_stability_resets_counter(setup):
    controller = instance(setup)
    launches = []
    setup.monkeypatch.setattr(controller, "launch", lambda job, row: launches.append(job["key"]))
    controller.dispatch()
    setup.rows[3]["free_mib"] = 1
    setup.rows[7]["free_mib"] = 1
    controller.dispatch()
    setup.rows[3]["free_mib"] = 31000
    controller.dispatch()
    assert launches == []
    controller.dispatch()
    assert launches == ["extension-test-seed11-c_only"]


def test_clean_admission_refusal_defers_without_global_failure(setup):
    controller = instance(setup)
    child = worker(setup, controller.jobs[0], rc=1)
    controller.children[child["job"]["key"]] = child
    controller.reap()
    assert not controller.children and not controller.failures
    assert controller.rejections == {child["job"]["key"]: 1}
    assert c.checked(child["attempt"] / "defer/record.json")["cooldown_seconds"] == 60
    assert c.checked(child["attempt"] / "exit/record.json")["completed"] is False
    with pytest.raises(ValueError, match="cooldown"):
        controller.launch(child["job"], setup.rows[3])


def test_clean_refusal_can_start_only_new_receipted_attempt(setup):
    controller = instance(setup)
    child = worker(setup, controller.jobs[0], rc=1)
    controller.children[child["job"]["key"]] = child
    controller.reap()
    old_exit = c.entry(child["attempt"] / "exit/record.json")
    controller.cooldowns[child["job"]["key"]] = 0
    setup.monkeypatch.setattr(
        c.subprocess, "Popen", lambda *args, **kw: SimpleNamespace(pid=88888, poll=lambda: None)
    )
    assert controller.launch(child["job"], setup.rows[3])
    receipt = c.checked(child["attempt"].parent / "attempt002/launch/record.json")
    assert receipt["previous_execution_attempt"] == str(child["attempt"])
    assert c.entry(child["attempt"] / "exit/record.json") == old_exit


def test_non_admission_or_partial_scientific_work_fails_closed(setup):
    controller = instance(setup)
    child = worker(setup, controller.jobs[0], rc=1)
    controller.children[child["job"]["key"]] = child
    setup.proof.prove_clean_precompute_rejection = lambda *args: (_ for _ in ()).throw(
        ValueError("provider intent exists")
    )
    controller.reap()
    assert len(controller.failures) == 1 and not controller.children
    assert not (child["attempt"] / "defer/record.json").exists()
    with pytest.raises(ValueError, match="dispatch halted"):
        controller.launch(controller.jobs[2], setup.rows[3])


def test_owned_process_retained_when_launch_receipt_fails(setup):
    controller = instance(setup)
    original = c.publish
    setup.monkeypatch.setattr(
        c.subprocess, "Popen", lambda *args, **kw: SimpleNamespace(pid=88888, poll=lambda: None)
    )

    def broken(path, value):
        if Path(path).parent.name == "launch":
            raise OSError("receipt I/O failure")
        return original(path, value)

    setup.monkeypatch.setattr(c, "publish", broken)
    with pytest.raises(OSError):
        controller.launch(controller.jobs[0], setup.rows[3])
    assert controller.children[controller.jobs[0]["key"]]["pid"] == 88888


def test_explicit_resume_adopts_live_pid_birth_without_relaunch(setup):
    job = setup.science["jobs"][0]
    worker(setup, job)
    with pytest.raises(ValueError, match="explicit resume"):
        c.Controller(setup.root)
    controller = c.Controller(setup.root, resume=True)
    assert controller.children[job["key"]]["process"] is None
    controller.reap()
    assert job["key"] in controller.children and not controller.failures


def test_reused_pid_without_result_never_restarts(setup):
    job = setup.science["jobs"][0]
    worker(setup, job, birth="old-birth")
    controller = c.Controller(setup.root, resume=True)
    assert not controller.children and len(controller.failures) == 1


def test_detached_completed_worker_adopted_and_exit_bound(setup):
    job = setup.science["jobs"][0]
    child = worker(setup, job, birth="old-birth")
    c.publish(job["result"], dict(scientific="fixture completion"))
    controller = c.Controller(setup.root, resume=True)
    assert controller.completed == {job["key"]}
    assert c.checked(child["attempt"] / "exit/record.json")["completed"] is True


def test_closed_completion_is_not_recomputed(setup):
    job = setup.science["jobs"][0]
    child = worker(setup, job)
    c.publish(job["result"], dict(scientific="fixture completion"))
    close(setup, child, complete=True, code=0)
    controller = c.Controller(setup.root, resume=True)
    assert controller.completed == {job["key"]}
    assert not controller.children and not controller.failures


def test_unowned_result_rejected(setup):
    c.publish(setup.science["jobs"][0]["result"], dict(foreign="result"))
    with pytest.raises(ValueError, match="unowned"):
        instance(setup)


def test_resume_recovers_exit_proof_publication_gap(setup):
    child = worker(setup, setup.science["jobs"][0])
    close(setup, child)
    controller = c.Controller(setup.root, resume=True)
    assert not controller.failures
    assert c.checked(child["attempt"] / "defer/record.json")["proof"]["clean"] is True


def test_partial_launch_fails_without_popen(setup):
    job = setup.science["jobs"][0]
    c.publish(
        setup.root / "queue/jobs" / job["key"] / "attempt001/intent/record.json", dict(partial=True)
    )
    controller = c.Controller(setup.root, resume=True)
    assert len(controller.failures) == 1
    assert "partial" in controller.failures[0]["reason"]


def test_failure_drains_owned_live_children_before_blocked(setup):
    controller = instance(setup)
    child = worker(setup, controller.jobs[0], rc=None)
    controller.children[child["job"]["key"]] = child
    controller.failures.append(dict(reason="another worker failed"))
    phases = []
    setup.monkeypatch.setattr(controller, "status", lambda phase: phases.append(phase))
    polls = []

    def advance(_):
        polls.append(1)
        c.publish(child["job"]["result"], dict(completed=True))
        child["process"].poll = lambda: 0

    setup.monkeypatch.setattr(c.time, "sleep", advance)
    controller.run()
    assert polls == [1]
    assert phases == ["DRAINING_AFTER_FAILURE", "DRAINING_AFTER_FAILURE", "BLOCKED_SAVED"]
    assert not controller.children


def test_scoring_barriers_never_read_effects_or_gate_training(setup):
    controller = instance(setup)
    calls = []
    setup.legacy.cpu_command = lambda *args: calls.append(args)
    controller.completed = {
        j["key"] for j in controller.jobs if j["branch"] == "c_only_test_extension"
    }
    controller.score_ready_blocks()
    assert len(calls) == 1 and calls[0][2] == [
        "score",
        "--root",
        str(setup.source / "c_only_test_extension"),
    ]
    assert {
        j["key"] for j, _ in c.assignments(controller.jobs, controller.completed, set(), setup.rows)
    } == {"replication-prefix-seed137"}


def test_status_stays_in_execution_root(setup):
    controller = instance(setup)
    original = c.file_entry(setup.source / "queue/status.json")
    controller.status("WAITING_FOR_RESOURCES")
    assert json.loads((setup.root / "queue/status.json").read_text())["total_jobs"] == 24
    assert c.file_entry(setup.source / "queue/status.json") == original


def test_exact_legacy_adoption_keeps_prefix_and_seals_without_computation(setup):
    wanted = {
        "extension-test-seed11-c_only",
        "extension-test-seed29-c_only",
        "replication-prefix-seed137",
    }
    refused = {"extension-test-seed47-c_only", "replication-prefix-seed251"}
    setup.legacy.process_birth = lambda pid: None
    for job in setup.science["jobs"]:
        if job["key"] not in wanted | refused:
            continue
        attempt = setup.source / "queue/jobs" / job["key"] / "attempt001"
        c.publish(
            attempt / "launch/record.json",
            dict(protocol_id=setup.science["id"], job=job, pid=77777, birth="12345"),
        )
        if job["key"] in wanted:
            if job["kind"] == "test":
                result = dict(
                    denominator=1147,
                    episode_sha256=["CPU fixture"] * 1147,
                    all_generation_complete=True,
                    all_provider_calls_settled=True,
                )
            else:
                result = dict(
                    actual_new_updates=298, migration_optimizer_steps=0, complete_prefix=True
                )
                for name in ("prefix_checkpoint", "shared_checkpoint"):
                    checkpoint = setup.source / name
                    checkpoint.mkdir()
                    (checkpoint / "state.pt").write_bytes(b"not a real state")
                    result[name] = dict(
                        path=str(checkpoint),
                        state_sha256=c.file_entry(checkpoint / "state.pt")["sha256"],
                    )
            c.publish(job["result"], result)
        c.publish(
            attempt / "exit/record.json",
            dict(
                protocol_id=setup.science["id"],
                key=job["key"],
                completed=job["key"] in wanted,
                result=c.entry(job["result"]) if job["key"] in wanted else None,
            ),
        )
    states = c.origin_state(setup.science, setup.legacy, setup.proof)
    assert {k for k, v in states.items() if v["state"] == "completed_adopted"} == wanted
    assert {k for k, v in states.items() if v["state"] == "clean_precompute_rejection"} == refused
    assert sum(v["state"] == "never_dispatched" for v in states.values()) == 19
    assert not (setup.root / "queue/jobs").exists()
    # Migration is read-only; changing even a retained checkpoint fails closed.
    (setup.source / "shared_checkpoint/state.pt").write_bytes(b"changed")
    with pytest.raises(ValueError, match="prefix checkpoint changed"):
        c.origin_state(setup.science, setup.legacy, setup.proof)


def test_legacy_completed_origin_cannot_create_continuation_attempt(setup):
    job = setup.science["jobs"][0]
    c.publish(job["result"], dict(completion="fixture"))
    plan = {k: v for k, v in setup.plan.items() if k != "id"}
    plan["origins"][job["key"]] = dict(
        state="completed_adopted", origin_attempt=None, result=c.entry(job["result"])
    )
    (setup.root / "protocol/record.json").write_text(json.dumps(plan | {"id": c.digest(plan)}))
    controller = instance(setup)
    assert controller.completed == {job["key"]}
    with pytest.raises(ValueError, match="repeated job"):
        controller.launch(job, setup.rows[3])
    assert not (setup.root / "queue/jobs").exists()
