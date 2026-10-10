"""CPU-only fixed three-task scope, source inheritance and admission checks."""

import copy
import importlib
import json
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest

sys.path.insert(0, str(Path(__file__).parents[1] / "scripts"))
queue = importlib.import_module("finqa_v36_controller")


class Clock:
    def __init__(self):
        self.wall, self.mono = 12_000.0, 1_000.0

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
    previous, root = source / "recovery_01", source / "recovery_02"
    previous.mkdir(parents=True)
    root.mkdir()
    monkeypatch.setattr(queue, "SOURCE", source)
    monkeypatch.setattr(queue, "PREVIOUS", previous)
    monkeypatch.setattr(queue, "ROOT", root)
    clock = Clock()
    monkeypatch.setattr(queue, "time", clock)
    monkeypatch.setattr(queue.base, "time", clock)
    monkeypatch.setattr(queue.base, "birth", lambda _: None)
    tasks = [dict(index=i, task_id=f"task{i}", shard=i % 4, row_count=1) for i in range(744)]
    for i in (739, 743):
        tasks[i]["shard"] = 1
    for i in (733, 737):
        tasks[i]["shard"] = 3
    for i, rows in zip((739, 741, 743), (8, 9, 9), strict=True):
        tasks[i]["row_count"] = rows
    task_plan = queue.publish(
        source / "task_plan/record.json",
        dict(
            task_ids=[t["task_id"] for t in tasks],
            tasks=tasks,
            parameter_spec=[dict(name="weight", shape=[2], dtype="torch.float32")],
            assignments=[
                dict(shard=i, task_ids=[t["task_id"] for t in tasks if t["shard"] == i])
                for i in range(4)
            ],
        ),
    )
    original = queue.publish(
        source / "protocol/record.json",
        dict(
            task_plan=queue.entry(source / "task_plan/record.json"),
            task_binding=dict(schema="original-math", implementation_id="original-seal"),
            implementation_id="original-seal",
            output_root=str(source),
            original_B_resume_authorized=False,
            gpu_uuids={str(i): f"GPU-{i}" for i in queue.base.ALLOWED_GPUS},
            source_commit="a" * 40,
        ),
    )
    previous_protocol = queue.publish(
        previous / "protocol/record.json",
        dict(
            task_plan=original["task_plan"],
            task_binding=original["task_binding"],
            output_root=str(previous),
            original_B_resume_authorized=False,
        ),
    )

    def original_protocol(path):
        assert Path(path) == source
        return copy.deepcopy(original)

    monkeypatch.setattr(queue.base, "checked_protocol", original_protocol)
    for index, parent in enumerate((source, previous)):
        queue.publish(
            parent / "failure/record.json",
            dict(
                protocol_id=(original if index == 0 else previous_protocol)["id"],
                error="original failure must remain unchanged",
                original_B_resume_authorized=False,
            ),
        )
        queue.base.status(
            parent,
            dict(
                phase="STOPPED_FAILURE_NO_RETRY",
                active_children=[],
                resource_wait_seconds=10 + 10 * index,
            ),
        )
        queue.publish(parent / "launch_01/record.json", dict(pid=100 + index, birth=f"old-{index}"))
        for j, stage in enumerate(queue.base.SHARD_STAGES):
            if index == 1 and stage == "shard00":
                continue
            queue.publish(
                parent / stage / "launch/record.json",
                dict(pid=200 + 10 * index + j, birth=f"worker-{index}-{j}"),
            )
    queue.publish(
        source / "execution_window/record.json",
        dict(protocol_id=original["id"], first_launch_epoch=100.0, deadline_epoch=14_500.0),
    )
    closeout = queue.publish(
        previous / "closeout_01/record.json",
        dict(
            durable_complete_tasks=741,
            durable_complete_rows=4948,
            global_coordinator_launched=False,
            original_protocol=queue.entry(source / "protocol/record.json"),
            recovery_protocol=queue.entry(previous / "protocol/record.json"),
            original_failure=queue.entry(source / "failure/record.json"),
            recovery_failure=queue.entry(previous / "failure/record.json"),
            total_elapsed_worker_wall_seconds=27_000.0,
        ),
    )
    monkeypatch.setattr(queue, "CLOSEOUT_ID", closeout["id"])
    for stage, parent, protocol in (
        ("shard00", source, original),
        ("shard02", previous, previous_protocol),
        ("shard03", previous, previous_protocol),
    ):
        queue.publish(
            parent / stage / "result/record.json",
            dict(protocol_id=protocol["id"], stage=stage, status="COMPLETE"),
        )
        queue.publish(parent / stage / "exit/record.json", dict(returncode=0))
    math = queue.publish(
        source / "implementation/record.json",
        dict(sha256={f"math{i:02d}.py": f"original-{i}" for i in range(19)}),
    )
    monkeypatch.setattr(queue.base, "checked_implementation", lambda _: copy.deepcopy(math))
    directory = root / "recovery_implementation"
    directory.mkdir()
    for name in queue.NEW_FILES:
        (directory / name).write_text("# mock committed controller: " + name)
    queue.publish(
        directory / "record.json",
        dict(
            schema="v36_lifecycle_overlay_implementation.v1",
            source_commit="b" * 40,
            mathematical_implementation=queue.entry(source / "implementation/record.json"),
            sha256={name: queue.sha(directory / name) for name in queue.NEW_FILES},
        ),
    )
    audit = root / "audit/source.txt"
    audit.parent.mkdir()
    audit.write_text("fixed three-task audit fixture")
    queue.publish(
        root / "audit/record.json",
        dict(source=queue.file_ref(audit), original_attachment=queue.file_ref(audit)),
    )
    queue.publish(root / "authorization/record.json", queue.authority(root))
    queue.publish(
        root / "cache_index/record.json",
        dict(parent_task_count=741, missing_indices=[739, 741, 743], parent_read_only=True),
    )
    protocol = queue.publish(
        root / "protocol/record.json", queue.protocol_body(root, original, at="test")
    )
    queue.publish(
        root / "execution_window/record.json",
        dict(
            protocol_id=protocol["id"],
            first_launch_epoch=100.0,
            deadline_epoch=14_500.0,
            source_window=queue.entry(source / "execution_window/record.json"),
            additional_runtime_window_seconds=0,
        ),
    )
    checks = []

    def check_result(given, stage, result, plan):
        assert result["protocol_id"] == given["id"] and result["stage"] == stage
        assert result["status"] == "COMPLETE" and plan == task_plan
        checks.append((given["id"], stage))
        return result

    monkeypatch.setattr(queue.base, "check_result", check_result)
    return SimpleNamespace(
        root=root,
        source=source,
        previous=previous,
        original=original,
        previous_protocol=previous_protocol,
        protocol=protocol,
        task_plan=task_plan,
        clock=clock,
        checks=checks,
        math=math,
    )


def reseal(path, **changes):
    record = queue.checked(path)
    record.update(changes)
    record.pop("id")
    record["id"] = queue.base.digest(record)
    path.write_text(json.dumps(record))  # Test tampering, never production behavior.
    return record


def test_registered_three_task_contract_preserves_parent_math_and_running_limits(registration):
    f = registration
    before = [(p / "failure/record.json").read_bytes() for p in (f.source, f.previous)]
    protocol = queue.checked_protocol(f.root)
    assert protocol["stages"] == ["shard01", "coordinator"]
    assert protocol["maximum_workers"] == protocol["max_gpu_workers"] == 1
    assert protocol["new_task_indices"] == [739, 741, 743]
    assert protocol["new_class_task_calls"] == 3 and protocol["new_complete_task_rows"] == 26
    assert protocol["task_binding"] == f.original["task_binding"]
    assert protocol["implementation_id"] == f.original["implementation_id"]
    host = protocol["host_ram"]
    assert host["shard_admission_bytes"] == 256 * queue.base.GIB
    assert host["coordinator_admission_bytes"] == 288 * queue.base.GIB
    assert host["shard_rss_limit_bytes"] == 160 * queue.base.GIB
    assert host["coordinator_rss_limit_bytes"] == 192 * queue.base.GIB
    assert host["reserve_bytes"] == 96 * queue.base.GIB
    assert before == [(p / "failure/record.json").read_bytes() for p in (f.source, f.previous)]


@pytest.mark.parametrize(
    "changes",
    [
        dict(deadline_epoch=28_900.0),
        dict(first_launch_epoch=12_000.0),
        dict(additional_runtime_window_seconds=14_400),
    ],
)
def test_resealed_window_cannot_reset_or_extend_original_deadline(registration, changes):
    reseal(registration.root / "execution_window/record.json", **changes)
    with pytest.raises(ValueError, match="absolute execution window changed"):
        queue.checked_protocol(registration.root)


@pytest.mark.parametrize(
    "changes",
    [
        dict(maximum_workers=2),
        dict(stages=["shard00", "coordinator"]),
        dict(new_class_task_calls=4),
        dict(task_binding={"rebound": True}),
    ],
)
def test_even_resealed_protocol_cannot_expand_work_or_rebind_math(registration, changes):
    reseal(registration.root / "protocol/record.json", **changes)
    with pytest.raises(ValueError, match="fixed V36 contract changed"):
        queue.checked_protocol(registration.root)


def test_changed_nineteen_file_math_copy_is_rejected(registration, monkeypatch):
    monkeypatch.setattr(
        queue.base,
        "checked_implementation",
        lambda path: (
            registration.math
            if Path(path) == registration.source
            else {**registration.math, "id": "changed"}
        ),
    )
    with pytest.raises(ValueError, match="mathematical seal changed"):
        queue.checked_math_implementation(registration.root)


def test_controller_inherits_only_actual_successful_stage_results_despite_failed_parents(
    registration,
):
    f = registration
    controller = queue.Controller(f.root)
    assert set(controller.results) == {"shard00", "shard02", "shard03"}
    assert f.checks == [
        (f.original["id"], "shard00"),
        (f.previous_protocol["id"], "shard02"),
        (f.previous_protocol["id"], "shard03"),
    ]
    assert controller.deadline_epoch == 14_500.0 and controller.first_launch_epoch == 100.0
    assert controller.deadline == 3_500.0
    assert controller.wait_used == 20  # Previous wait already includes the source's 10 seconds.
    assert all(
        json.loads((p / "queue/status.json").read_bytes())["phase"] == "STOPPED_FAILURE_NO_RETRY"
        for p in (f.source, f.previous)
    )


def test_inherited_stage_requires_actual_clean_exit(registration):
    reseal(registration.previous / "shard02/exit/record.json", returncode=1)
    with pytest.raises(ValueError, match="did not exit successfully"):
        queue.Controller(registration.root)


@pytest.mark.parametrize("which", ["source", "previous"])
def test_previous_coordinator_or_live_process_blocks_new_attempt(registration, which, monkeypatch):
    parent = getattr(registration, which)
    (parent / "coordinator").mkdir()
    with pytest.raises(ValueError, match="global recomputation previously attempted"):
        queue.checked_parents()


def test_live_parent_controller_is_rejected(registration, monkeypatch):
    monkeypatch.setattr(queue.base, "birth", lambda pid: "old-1" if pid == 101 else None)
    with pytest.raises(ValueError, match="prior controller still alive"):
        queue.checked_parents()


@pytest.mark.parametrize("stage", ["shard00", "shard02", "shard03"])
def test_other_shards_cannot_be_dispatched(registration, stage):
    controller = queue.Controller(registration.root)
    with pytest.raises(ValueError, match="single dispatch"):
        controller.launch(stage, {"index": queue.base.STAGE_GPU[stage]}, object())


def test_live_or_draining_slot_blocks_another_admission_and_dispatch(registration):
    controller = queue.Controller(registration.root)
    controller.active["shard01"] = {"state": "DRAINING_TRUSTED_RESULT"}
    with pytest.raises(ValueError, match="single worker admission"):
        controller.acquire(("coordinator",))
    with pytest.raises(ValueError, match="single dispatch"):
        controller.launch("coordinator", dict(index=7), object())


def test_coordinator_requires_completed_shard_and_whole_cache_receipt(registration):
    controller = queue.Controller(registration.root)
    with pytest.raises(ValueError, match="coordinator not admitted"):
        controller.launch("coordinator", dict(index=7), object())


def test_shard_result_requires_exact_three_new_calls_and_twenty_six_rows(registration):
    controller = queue.Controller(registration.root)
    reused = [
        t["task_id"]
        for t in registration.task_plan["tasks"]
        if t["shard"] == 1 and t["index"] not in queue.MISSING_INDICES
    ]
    assert len(reused) == 183
    result = dict(
        protocol_id=registration.protocol["id"],
        stage="shard01",
        status="COMPLETE",
        reused_task_ids=reused,
        class_task_calls=3,
        new_completed_rows=26,
        cache_tensor_verification=tensor_receipt(registration, "shard01"),
    )
    assert controller.lifecycle_result_validator("shard01", result) is result
    for changes in (
        dict(class_task_calls=4),
        dict(new_completed_rows=19),
        dict(reused_task_ids=reused[1:]),
    ):
        with pytest.raises(ValueError, match="three-task supplement"):
            controller.lifecycle_result_validator("shard01", result | changes)


def tensor_receipt(registration, stage, **changes):
    parent, local = (183, 0) if stage == "shard01" else (741, 3)
    number = len(list(registration.root.glob("tensor_receipt*")))
    path = registration.root / f"tensor_receipt{number}/record.json"
    queue.publish(
        path,
        dict(
            schema="v36_actual_cache_tensor_verification.v1",
            protocol_id=registration.protocol["id"],
            stage=stage,
            index_id=queue.checked(registration.root / "cache_index/record.json")["id"],
            parent_tasks_strictly_verified=parent,
            local_tasks_strictly_verified=local,
            strict_payload_file_reads=parent + local,
            process_id=123,
            cross_process_verification_waiver=False,
            parent_gradient_payload_bytes_copied=0,
        )
        | changes,
    )
    return queue.entry(path)


def test_coordinator_requires_actual_741_parent_and_three_local_tensor_reads(registration):
    controller = queue.Controller(registration.root)
    result = dict(
        protocol_id=registration.protocol["id"],
        stage="coordinator",
        status="COMPLETE",
        cache_tensor_verification=tensor_receipt(registration, "coordinator"),
    )
    assert controller.lifecycle_result_validator("coordinator", result) is result
    for change in (
        dict(strict_payload_file_reads=741),
        dict(parent_tasks_strictly_verified=0),
        dict(local_tasks_strictly_verified=0),
        dict(index_id="foreign"),
    ):
        wrong = result | dict(
            cache_tensor_verification=tensor_receipt(registration, "coordinator", **change)
        )
        with pytest.raises(ValueError, match="tensor verification is incomplete or foreign"):
            controller.lifecycle_result_validator("coordinator", wrong)


def test_tensor_verification_receipt_must_come_from_dispatched_process(registration):
    controller = queue.Controller(registration.root)
    controller.active["coordinator"] = {"launch": {"pid": 456}}
    result = dict(
        protocol_id=registration.protocol["id"],
        stage="coordinator",
        status="COMPLETE",
        cache_tensor_verification=tensor_receipt(registration, "coordinator"),
    )
    with pytest.raises(ValueError, match="another worker"):
        controller.lifecycle_result_validator("coordinator", result)


def test_root_coverage_uses_read_only_overlay_inspector(registration, monkeypatch):
    controller = queue.Controller(registration.root)
    calls = []

    def inspect(root, *, complete):
        calls.append((root, complete))
        return dict(
            complete_task_count=744 if complete else 741, tensor_payloads_deserialized=False
        )

    def module(path, name):
        assert path == registration.root / "recovery_implementation/finqa_v36_cache.py"
        return SimpleNamespace(inspect_overlay=inspect)

    monkeypatch.setattr(queue, "_module", module)
    assert controller.validate_task_coverage(complete=True)["complete_task_count"] == 744
    assert controller.validate_task_coverage(complete=False)["complete_task_count"] == 741
    assert calls == [(registration.root, True), (registration.root, False)]


@pytest.mark.parametrize("stage,admission_gib", [("shard01", 256), ("coordinator", 288)])
def test_single_process_host_admission_uses_registered_not_four_worker_budget(
    registration, monkeypatch, stage, admission_gib
):
    controller = queue.Controller(registration.root)
    index = queue.base.STAGE_GPU[stage]
    rows = [dict(index=index, uuid=f"GPU-{index}")]
    monkeypatch.setattr(queue.base, "inventory", lambda: rows)
    monkeypatch.setattr(queue.base, "eligible", lambda _row, _protocol: True)
    monkeypatch.setattr(
        queue.shutil, "disk_usage", lambda _: SimpleNamespace(free=1000 * queue.base.GIB)
    )
    monkeypatch.setattr(
        queue.base, "host_memory", lambda: dict(available_bytes=admission_gib * queue.base.GIB)
    )
    acquired, locks = controller.acquire((stage,))
    assert acquired[index]["uuid"] == f"GPU-{index}" and set(locks) == {index}
    locks[index].close()


def test_expired_source_window_blocks_registration_before_freeze(registration, monkeypatch):
    target = registration.source / "not-created"
    monkeypatch.setattr(queue, "ROOT", target)
    registration.clock.wall = 14_500
    monkeypatch.setattr(
        queue.subprocess, "check_output", lambda *_a, **_k: pytest.fail("no freeze after deadline")
    )
    with pytest.raises(ValueError, match="window expired"):
        queue.initialize(target, "commit")
    assert not target.exists()
