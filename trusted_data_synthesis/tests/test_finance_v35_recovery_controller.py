"""CPU-only same-window recovery scope, immutable binding and shell tests."""

import copy
import importlib
import json
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest

sys.path.insert(0, str(Path(__file__).parents[1] / "scripts"))
queue = importlib.import_module("finqa_v35_recovery_controller")


class Clock:
    def __init__(self):
        self.wall = 12_000.0
        self.mono = 1_000.0

    def time(self):
        return self.wall

    def monotonic(self):
        return self.mono

    def sleep(self, seconds):
        self.wall += seconds
        self.mono += seconds


@pytest.fixture
def registration(tmp_path, monkeypatch):
    source = tmp_path / "source"
    root = source / "recovery_01"
    source.mkdir()
    root.mkdir()
    monkeypatch.setattr(queue, "SOURCE_ROOT", source)
    monkeypatch.setattr(queue, "ROOT", root)
    clock = Clock()
    monkeypatch.setattr(queue, "time", clock)
    monkeypatch.setattr(queue.base, "time", clock)
    monkeypatch.setattr(queue.base, "birth", lambda _: None)
    task_plan = queue.publish(
        source / "task_plan/record.json",
        dict(
            task_ids=["a", "b", "c", "d"],
            assignments=[dict(shard=i, task_ids=[task]) for i, task in enumerate("abcd")],
        ),
    )
    original = queue.publish(
        source / "protocol/record.json",
        dict(
            task_plan=queue.entry(source / "task_plan/record.json"),
            task_binding=dict(schema="original_math", implementation_id="original-implementation"),
            implementation_id="original-implementation",
            output_root=str(source),
            original_B_resume_authorized=False,
            gpu_uuids={str(i): f"GPU-{i}" for i in queue.base.ALLOWED_GPUS},
            source_commit="a" * 40,
        ),
    )
    monkeypatch.setattr(queue, "SOURCE_PROTOCOL_ID", original["id"])

    def original_protocol(path):
        assert Path(path) == source
        return copy.deepcopy(original)

    monkeypatch.setattr(queue.base, "checked_protocol", original_protocol)
    queue.publish(
        source / "failure/record.json",
        dict(protocol_id=original["id"], error="live worker RSS unavailable"),
    )
    queue.publish(
        source / "execution_window/record.json",
        dict(protocol_id=original["id"], first_launch_epoch=100.0, deadline_epoch=14_500.0),
    )
    queue.base.status(
        source,
        dict(
            phase="STOPPED_FAILURE_NO_RETRY",
            protocol_id=original["id"],
            active_children=[],
            error="live worker RSS unavailable",
            resource_wait_seconds=22.0,
            worker_accounting=dict(total_elapsed_worker_hours=6.5),
        ),
    )
    for index, relative in enumerate(
        ("queue/run_intent", *(s + "/launch" for s in queue.base.SHARD_STAGES))
    ):
        queue.publish(
            source / relative / "record.json", dict(pid=10_000 + index, birth=f"old-{index}")
        )
    math = queue.publish(
        source / "implementation/record.json", dict(sha256={"math.py": "same-bytes"})
    )
    monkeypatch.setattr(queue.base, "checked_implementation", lambda _: copy.deepcopy(math))
    directory = root / "recovery_implementation"
    directory.mkdir()
    for name in queue.FILES:
        (directory / name).write_text("# mock committed shell: " + name)
    queue.publish(
        directory / "record.json",
        dict(
            schema="v35_separate_recovery_control_implementation.v1",
            source_commit="b" * 40,
            original_math_implementation=queue.entry(source / "implementation/record.json"),
            sha256={name: queue.sha(directory / name) for name in queue.FILES},
        ),
    )
    queue.publish(
        source / "shard00/result/record.json",
        dict(protocol_id=original["id"], stage="shard00", status="COMPLETE"),
    )
    queue.publish(source / "shard00/exit/record.json", dict(returncode=0))
    queue.publish(
        root / "cache_inheritance/record.json",
        dict(
            inherited_completed_stages=dict(
                shard00=dict(
                    result=queue.entry(source / "shard00/result/record.json"),
                    exit=queue.entry(source / "shard00/exit/record.json"),
                )
            ),
            complete_tasks_reused=674,
            missing_tasks=70,
            by_shard=[
                dict(
                    stage=f"shard{i:02d}",
                    complete_task_ids=[task] if i == 0 else [],
                    missing_task_ids=[] if i == 0 else [task],
                )
                for i, task in enumerate("abcd")
            ],
        ),
    )
    queue.publish(root / "authorization/record.json", queue.authorization_body())
    protocol = queue.publish(
        root / "protocol/record.json", queue.protocol_body(root, original, at="test")
    )
    queue.publish(
        root / "execution_window/record.json",
        dict(
            schema="v35_inherited_absolute_execution_window.v1",
            at="test",
            protocol_id=protocol["id"],
            first_launch_epoch=100.0,
            deadline_epoch=14_500.0,
            source_window=queue.entry(source / "execution_window/record.json"),
            additional_runtime_window_seconds=0,
            no_stage_deadline_reset=True,
        ),
    )
    checks = []

    def check_result(given_protocol, stage, result, given_plan):
        assert result["protocol_id"] == given_protocol["id"]
        assert result["stage"] == stage and given_plan == task_plan
        checks.append((given_protocol["id"], stage))
        return result

    monkeypatch.setattr(queue.base, "check_result", check_result)
    return SimpleNamespace(
        root=root,
        source=source,
        original=original,
        protocol=protocol,
        task_plan=task_plan,
        clock=clock,
        checks=checks,
        math=math,
    )


def rewrite_sealed(path, **changes):
    value = queue.checked(path)
    value.update(changes)
    value.pop("id")
    value["id"] = queue.base.digest(value)
    # Deliberate test tampering; production records are never rewritten.
    path.write_text(json.dumps(value))
    return value


def test_same_absolute_window_and_original_math_binding_survive_registration(registration):
    fixture = registration
    old_failure = (fixture.source / "failure/record.json").read_bytes()
    actual = queue.checked_protocol(fixture.root)
    assert actual["absolute_deadline_epoch"] == 14_500
    assert actual["task_binding"] == fixture.original["task_binding"]
    assert actual["implementation_id"] == fixture.original["implementation_id"]
    assert actual["recovery_stages"] == ["shard01", "shard02", "shard03"]
    assert actual["original_V35_failure_reclassified"] is False
    assert (fixture.source / "failure/record.json").read_bytes() == old_failure


@pytest.mark.parametrize(
    "changes",
    [
        dict(deadline_epoch=28_900.0),
        dict(first_launch_epoch=12_000.0),
        dict(protocol_id="another-protocol"),
        dict(additional_runtime_window_seconds=14_400),
    ],
)
def test_even_resealed_recovery_window_cannot_reset_original_budget(registration, changes):
    rewrite_sealed(registration.root / "execution_window/record.json", **changes)
    with pytest.raises(ValueError):
        queue.checked_protocol(registration.root)


def test_recovery_shell_manifest_must_bind_exact_original_math_manifest(registration):
    rewrite_sealed(
        registration.root / "recovery_implementation/record.json",
        original_math_implementation=dict(path="elsewhere", sha256="wrong", id="other"),
    )
    with pytest.raises(ValueError):
        queue.checked_recovery_implementation(registration.root)


def test_math_copy_not_rebound_or_silently_changed(registration, monkeypatch):
    def changed(path):
        if Path(path) == registration.source:
            return registration.math
        return {**registration.math, "id": "changed-copy"}

    monkeypatch.setattr(queue.base, "checked_implementation", changed)
    with pytest.raises(ValueError, match="mathematical implementation differs"):
        queue.checked_math_implementation(registration.root)


def test_source_failure_and_unstarted_coordinator_are_mandatory(registration):
    coordinator = registration.source / "coordinator"
    coordinator.mkdir()
    with pytest.raises(ValueError, match="global recomputation already attempted"):
        queue.source_still_stopped(registration.original)


def test_original_live_worker_blocks_recovery(registration, monkeypatch):
    monkeypatch.setattr(queue.base, "birth", lambda pid: "old-0" if pid == 10_000 else None)
    with pytest.raises(ValueError, match="source process still alive"):
        queue.source_still_stopped(registration.original)


def test_constructor_reuses_clean_shard00_and_only_remaining_original_seconds(registration):
    controller = queue.RecoveryController(registration.root)
    assert set(controller.results) == {"shard00"}
    assert registration.checks == [(registration.original["id"], "shard00")]
    assert controller.deadline_epoch == 14_500
    assert controller.first_launch_epoch == 100
    assert controller.deadline == 3_500  # 1,000 monotonic + (14,500 - 12,000 wall)
    assert controller.wait_used == 22
    registration.clock.sleep(2_500)
    with pytest.raises(ValueError, match="shared global deadline"):
        controller.time_gate()


def test_completed_shard00_cannot_be_dispatched_again(registration):
    controller = queue.RecoveryController(registration.root)
    with pytest.raises(ValueError, match="completed shard00 must not relaunch"):
        controller.launch("shard00", dict(index=3), object())


def test_recovery_worker_argv_uses_wrapper_and_exact_deadline(registration, monkeypatch):
    seen = []
    old_worker = str(registration.root / "implementation/finqa_v35_task_worker.py")

    def old_command(root, stage, row, protocol, deadline):
        seen.append((root, stage, deadline))
        return ["python", old_worker, "--deadline-epoch", str(deadline)]

    monkeypatch.setattr(queue.base, "worker_command", old_command)
    actual = queue.worker_command(
        registration.root, "shard02", dict(index=5), registration.protocol, 14_500
    )
    assert actual == [
        "python",
        str(registration.root / "recovery_implementation/finqa_v35_recovery_worker.py"),
        "--deadline-epoch",
        "14500",
    ]
    assert seen == [(registration.root, "shard02", 14_500)]


def test_inherited_collector_validates_new_protocol_and_retains_old_stage(
    registration, monkeypatch
):
    controller = queue.RecoveryController(registration.root)
    stage = "shard01"
    queue.publish(
        registration.root / stage / "result/record.json",
        dict(
            stage=stage,
            protocol_id=registration.protocol["id"],
            status="COMPLETE",
            reused_task_ids=[],
            class_task_calls=1,
        ),
    )
    process = SimpleNamespace(poll=lambda: 0, wait=lambda: 0)
    lock = SimpleNamespace(close=lambda: None)
    controller.active[stage] = dict(
        process=process,
        lock=lock,
        started_monotonic=900,
        launch=dict(stage=stage, pid=50, birth="b", gpu_index=4, gpu_uuid="GPU-4"),
    )
    controller.collect_finished()
    assert not controller.active and set(controller.results) == {"shard00", "shard01"}
    assert registration.checks == [
        (registration.original["id"], "shard00"),
        (registration.protocol["id"], "shard01"),
    ]
    accounting = controller.worker_accounting()
    assert accounting["original_plus_recovery_exited_worker_hours"] == 6.5 + 100 / 3600


def test_expired_original_window_prevents_registration_before_any_freeze(registration, monkeypatch):
    target = registration.source / "different_recovery"
    monkeypatch.setattr(queue, "ROOT", target)
    registration.clock.wall = 14_500
    monkeypatch.setattr(
        queue.subprocess,
        "check_output",
        lambda *a, **k: pytest.fail("must not freeze after deadline"),
    )
    with pytest.raises(ValueError, match="original absolute deadline already expired"):
        queue.initialize(target, "some-commit")
    assert not target.exists()


@pytest.mark.parametrize("reused,calls", [(["b"], 0), ([], 2), ([], 0)])
def test_recovery_collector_rejects_extra_or_missing_task_work(registration, reused, calls):
    controller = queue.RecoveryController(registration.root)
    controller.results["shard01"] = dict(reused_task_ids=reused, class_task_calls=calls)
    with pytest.raises(ValueError, match="recomputed inherited tasks or omitted missing"):
        controller.collect_finished()
