"""CPU-only release-boundary and checkpoint-resume tests; never real signals."""

import importlib.util
from pathlib import Path
from types import SimpleNamespace

import pytest

SCRIPTS = Path(__file__).resolve().parents[1] / "scripts"
spec = importlib.util.spec_from_file_location(
    "v29_test", SCRIPTS / "finqa_v29_retained_gpu_controller.py"
)
c = importlib.util.module_from_spec(spec)
spec.loader.exec_module(c)


def forbid(*args, **kwargs):
    raise AssertionError("fixture must not start a real process")


@pytest.fixture
def fixture(tmp_path, monkeypatch):
    source, root = tmp_path / "v25", tmp_path / "v25/four_gpu_release_01"
    job = dict(
        key="replication-train-seed389-static",
        kind="arm",
        dependencies=[],
        args=["train", "--seed", "389", "--arm", "static"],
        branch="training_replication",
        script="finqa_v25_training_replication.py",
        result=str(source / "static/result/record.json"),
    )
    rows = [
        dict(index=i, uuid=f"GPU-fixture-{i}", free_mib=81154, cpu_affinity="0-3") for i in range(8)
    ]
    obj = object.__new__(c.RetainedMixin)
    obj.root, obj.jobs = root, [job]
    obj.completed, obj.children, obj.failures = set(), {}, []
    obj.stop = False
    obj.cooldowns, obj.rejections, obj.observations = {}, {}, {}
    obj.pending_checkpoint_resumes, obj.checkpoint_recoveries = {}, {}
    obj.science = dict(
        id="science",
        gpu_uuids={str(i): row["uuid"] for i, row in enumerate(rows)},
        cpu_affinity={str(i): row["cpu_affinity"] for i, row in enumerate(rows)},
        dispatch_disk_floor_bytes=1024,
    )
    obj.plan = dict(
        id="plan", origins={job["key"]: dict(state="never_dispatched", origin_attempt=None)}
    )
    obj.legacy = SimpleNamespace(
        inventory=lambda: rows,
        disk_available=lambda _: 10**12,
        process_birth=lambda _: "birth",
        PYTHON=Path("/fixture/python"),
        FROZEN=source,
        command_environment=lambda: {},
        atomic_status=lambda root, value: setattr(obj, "last_status", value),
    )
    base = c.v28.predecessor_module()
    obj.base = SimpleNamespace(assignments=base.assignments)
    monkeypatch.setattr(c, "SOURCE_ROOT", source)
    monkeypatch.setattr(c, "ROOT", root)
    monkeypatch.setattr(c.v28, "compute_processes", lambda: set())
    monkeypatch.setattr(c.subprocess, "Popen", forbid)
    return SimpleNamespace(
        obj=obj, source=source, root=root, job=job, rows=rows, monkeypatch=monkeypatch
    )


@pytest.mark.parametrize("gpu", [0, 1, 2, 6])
def test_direct_launch_cannot_reclaim_non_idle_released_gpu(fixture, gpu):
    fixture.monkeypatch.setattr(c.v28, "compute_processes", lambda: {fixture.rows[gpu]["uuid"]})
    assert fixture.obj.launch(fixture.job, fixture.rows[gpu]) is False
    assert not fixture.root.exists()


def test_dispatch_never_considers_released_cards_even_if_only_they_have_memory(fixture):
    for gpu in c.RETAINED_AT_RELEASE:
        fixture.rows[gpu]["free_mib"] = 0
    fixture.monkeypatch.setattr(
        c.v28, "compute_processes", lambda: {fixture.rows[gpu]["uuid"] for gpu in c.RELEASED_GPUS}
    )
    fixture.obj.launch = forbid
    fixture.obj.dispatch()
    fixture.obj.dispatch()
    assert all(count == 0 for count in fixture.obj.observations.values())


def test_dispatch_retained_card_requires_two_observations(fixture):
    selected = []
    fixture.obj.launch = lambda job, row: selected.append(row["index"])
    fixture.obj.dispatch()
    assert selected == []
    fixture.obj.dispatch()
    assert len(selected) == 1 and selected[0] in c.ALLOWED_GPUS


def checkpoint_fixture(fixture):
    job, obj = fixture.job, fixture.obj
    directory = fixture.source / "training_replication/seed389/arms/static/training/step0576_step"
    directory.mkdir(parents=True)
    (directory / "record.json").write_text('{"step": 576}')
    (directory / "state.pt").write_bytes(b"CPU fixture Adam RNG parameters")
    intent = directory.parents[1] / "launch_attempts/attempt001/intent/record.json"
    intent.parent.mkdir(parents=True)
    intent.write_text('{"seed": 389}')
    proof = dict(
        eligible=True,
        job_key=job["key"],
        no_feedback_resampling=True,
        checkpoint=dict(
            metadata=c.file_entry(directory / "record.json"),
            state=c.file_entry(directory / "state.pt"),
        ),
        arm_file_inventory={
            str(path.relative_to(directory.parents[1])): {
                **c.file_entry(path),
                "bytes": path.stat().st_size,
            }
            for path in directory.parents[1].rglob("*")
            if path.is_file()
        },
    )
    obj.plan["origins"][job["key"]] = dict(
        state="administrative_checkpoint_resume",
        proof=proof,
        origin_attempt="/fixture/old/attempt001",
    )
    return directory, proof


def fake_popen(fixture):
    seen = []
    fixture.monkeypatch.setattr(
        c.subprocess,
        "Popen",
        lambda command, **kwargs: seen.append(command) or SimpleNamespace(pid=1234),
    )
    return seen


def test_admin_resume_reuses_frozen_wrapper_and_original_arguments(fixture):
    _, proof = checkpoint_fixture(fixture)
    seen = fake_popen(fixture)
    assert fixture.obj.launch(fixture.job, fixture.rows[7]) is True
    command = seen[0]
    assert command[5] == str(c.WRAPPER)
    assert command[-1] == "--resume"
    assert command[command.index("--") + 1 :] == [
        *fixture.job["args"],
        "--root",
        str(fixture.source / fixture.job["branch"]),
        "--gpu-index",
        "7",
        "--resume",
    ]
    launch = c.checked(
        fixture.root / "queue/jobs" / fixture.job["key"] / "attempt001/launch/record.json"
    )
    assert launch["administrative_resume_authorization"] == proof
    assert launch["administrative_checkpoint_resume"] is True
    assert launch["automatic_checkpoint_resume"] is False
    assert launch["memory_mode"] == "high_cache"
    assert fixture.obj.checkpoint_recoveries == {}


def test_shared_card_administrative_resume_keeps_checkpointed_mode(fixture):
    checkpoint_fixture(fixture)
    fixture.rows[5]["free_mib"] = 60000
    fixture.monkeypatch.setattr(c.v28, "compute_processes", lambda: {fixture.rows[5]["uuid"]})
    seen = fake_popen(fixture)
    assert fixture.obj.launch(fixture.job, fixture.rows[5])
    assert seen[0][seen[0].index("--memory-mode") + 1] == "shared_checkpointed"
    assert seen[0][-1] == "--resume"


def test_changed_checkpoint_blocks_resume(fixture):
    directory, _ = checkpoint_fixture(fixture)
    (directory / "state.pt").write_bytes(b"changed")
    with pytest.raises(ValueError, match="checkpoint changed"):
        fixture.obj.launch(fixture.job, fixture.rows[7])
    assert not fixture.root.exists()


def test_partial_feedback_blocks_resume(fixture):
    directory, _ = checkpoint_fixture(fixture)
    feedback = directory.parents[1] / "feedback/partial_outer"
    feedback.mkdir(parents=True)
    with pytest.raises(ValueError, match="partial feedback"):
        fixture.obj.launch(fixture.job, fixture.rows[7])


@pytest.mark.parametrize("mutation", ["new_attempt", "changed_metadata", "deleted_metadata"])
def test_scientific_arm_inventory_cannot_change_while_paused(fixture, mutation):
    directory, _ = checkpoint_fixture(fixture)
    intent = directory.parents[1] / "launch_attempts/attempt001/intent/record.json"
    if mutation == "new_attempt":
        new = directory.parents[1] / "launch_attempts/attempt002/intent/record.json"
        new.parent.mkdir(parents=True)
        new.write_text("{}")
    elif mutation == "changed_metadata":
        intent.write_text('{"seed": 137}')
    else:
        intent.unlink()
    with pytest.raises(ValueError, match="paused arm (file inventory|metadata) changed"):
        fixture.obj.launch(fixture.job, fixture.rows[7])


def test_even_empty_feedback_directory_blocks_administrative_resume(fixture):
    directory, _ = checkpoint_fixture(fixture)
    (directory.parents[1] / "feedback").mkdir()
    with pytest.raises(ValueError, match="partial feedback"):
        fixture.obj.launch(fixture.job, fixture.rows[7])


def test_newer_checkpoint_requires_new_authorization(fixture):
    directory, _ = checkpoint_fixture(fixture)
    newer = directory.parent / "step0608_step"
    newer.mkdir()
    (newer / "record.json").write_text("{}")
    with pytest.raises(ValueError, match="newer checkpoint"):
        fixture.obj.launch(fixture.job, fixture.rows[7])


def test_admin_resume_cannot_run_twice(fixture):
    checkpoint_fixture(fixture)
    (fixture.root / "queue/jobs" / fixture.job["key"] / "attempt001").mkdir(parents=True)
    with pytest.raises(ValueError, match="already launched"):
        fixture.obj.launch(fixture.job, fixture.rows[7])


def test_status_hardcodes_retained_only_capacity(fixture):
    fixture.obj.status("WAITING_FOR_RESOURCES")
    assert fixture.obj.last_status["allowed_gpu_indices"] == list(range(8))
    assert fixture.obj.last_status["released_gpu_indices"] == [0, 1, 2, 6]
    assert fixture.obj.last_status["max_gpu_workers"] == 6
    assert fixture.obj.last_status["released_gpu_reuse_requires_idle_high_cache"] is True


def test_retained_adoption_preserves_memory_mode_without_starting_process(fixture):
    obj, job = fixture.obj, fixture.job
    old = c.publish(
        fixture.source / "predecessor/queue/jobs/static/attempt001/launch/record.json",
        dict(
            job=job,
            pid=1234,
            birth="birth",
            gpu=7,
            command=["python", "wrapper"],
            memory_mode="high_cache",
        ),
    )
    ref = c.entry(fixture.source / "predecessor/queue/jobs/static/attempt001/launch/record.json")
    obj.adopt(
        job,
        dict(
            origin_launch=ref,
            origin_attempt="/fixture/old",
            pid=1234,
            birth="birth",
            gpu=7,
            command=old["command"],
        ),
    )
    new = c.checked(fixture.root / "queue/jobs" / job["key"] / "attempt001/launch/record.json")
    assert new["memory_mode"] == "high_cache" and new["new_process_started"] is False
    assert obj.children[job["key"]]["pid"] == 1234


def test_incomplete_dependency_never_starts(fixture):
    fixture.job["dependencies"] = ["missing-prefix"]
    with pytest.raises(ValueError, match="unfinished dependency"):
        fixture.obj.launch(fixture.job, fixture.rows[7])


def test_six_worker_bound_blocks_seventh_direct_launch(fixture):
    fixture.obj.children = {str(i): dict(gpu=i) for i in range(6)}
    with pytest.raises(ValueError, match="six-GPU worker bound"):
        fixture.obj.launch(fixture.job, fixture.rows[7])


def test_dispatch_starts_only_two_when_four_already_owned(fixture):
    obj = fixture.obj
    obj.children = {str(i): dict(gpu=i) for i in c.RETAINED_AT_RELEASE}
    obj.jobs = [{**fixture.job, "key": "fresh" + str(i)} for i in range(4)]
    started = []

    def launch(job, row):
        started.append(row["index"])
        obj.children[job["key"]] = dict(gpu=row["index"])
        return True

    obj.launch = launch
    obj.dispatch()
    obj.dispatch()
    assert len(started) == 2 and len(obj.children) == 6


def test_restore_cannot_own_more_than_six(fixture):
    obj = fixture.obj
    obj.children = {str(i): dict(gpu=i) for i in range(6)}
    fixture.monkeypatch.setattr(
        c.v28.RecoveryMixin,
        "restore_job",
        lambda self, job, resume: self.children.update({job["key"]: dict(gpu=7)}),
    )
    with pytest.raises(ValueError, match="six-GPU restore worker bound"):
        obj.restore_job(fixture.job, True)


def test_released_card_can_be_reused_when_still_completely_idle(fixture):
    checkpoint_fixture(fixture)
    seen = fake_popen(fixture)
    assert fixture.obj.launch(fixture.job, fixture.rows[0])
    assert seen[0][seen[0].index("--memory-mode") + 1] == "high_cache"


def test_released_card_needs_eighty_thousand_mib_even_without_processes(fixture):
    fixture.rows[0]["free_mib"] = 79999
    assert fixture.obj.launch(fixture.job, fixture.rows[0]) is False
