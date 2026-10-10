"""CPU-only recovery provenance/copy gates; no production numerical claims."""

import copy
import hashlib
import importlib
import json
import sys
import time
from pathlib import Path
from types import SimpleNamespace

import pytest

sys.path.insert(0, str(Path(__file__).parents[1] / "scripts"))
recovery = importlib.import_module("finqa_v35_recovery_cache")
cache_module = importlib.import_module("finqa_v35_task_cache")


def publish(path, body):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    value = {**body, "id": cache_module.digest(body)}
    path.write_text(json.dumps(value))
    return value


def checked(path):
    return cache_module._checked_record(json.loads(Path(path).read_bytes()))


def file_ref(path):
    return dict(
        path=str(Path(path).resolve()), sha256=hashlib.sha256(Path(path).read_bytes()).hexdigest()
    )


def entry(path):
    return {**file_ref(path), "id": checked(path)["id"]}


def read_ref(ref):
    assert ref == entry(ref["path"])
    return checked(ref["path"])


def zeros():
    return {**dict.fromkeys(recovery.ZERO_KEYS, 0), "original_B_resume_authorized": False}


def observation(index, label, *, deadline, stopped=False):
    return dict(
        sequence=index,
        label=label,
        boundary=True,
        allocated_bytes=1024,
        reserved_bytes=2048,
        peak_allocated_bytes=1536,
        peak_reserved_bytes=2048,
        free_bytes=3 * recovery.GIB,
        total_bytes=80 * recovery.GIB,
        limits=dict(
            allocated_memory_limit_bytes=recovery.GPU_LIMIT,
            free_memory_reserve_bytes=recovery.FREE_RESERVE,
        ),
        allocated_pass=True,
        free_pass=True,
        stop_requested=stopped,
        passed=not stopped,
        deadline_epoch=deadline,
        deadline_pass=True,
        host=dict(
            rss_bytes=4 * recovery.GIB,
            peak_rss_bytes=5 * recovery.GIB,
            available_bytes=100 * recovery.GIB,
            rss_limit_bytes=recovery.HOST_LIMIT,
            available_reserve_bytes=recovery.HOST_RESERVE,
            rss_pass=True,
            available_pass=True,
            passed=True,
        ),
    )


@pytest.fixture
def fixture(tmp_path):
    source = tmp_path / "original"
    target = source / "recovery_01"
    task_ids = [f"task{i}" for i in range(8)]
    complete = ["task0", "task1", "task2", "task4", "task6"]
    missing = [task for task in task_ids if task not in complete]
    plan = publish(
        source / "task_plan/record.json",
        dict(
            schema="v35_complete_task_plan.v1",
            task_ids=task_ids,
            tasks=[
                dict(index=i, task_id=task, shard=i // 2, state_ids=["state"], row_count=2)
                for i, task in enumerate(task_ids)
            ],
            parameter_spec=[dict(name="weight", shape=[1], dtype="torch.float32")],
            assignments=[dict(shard=i, task_ids=task_ids[i * 2 : (i + 1) * 2]) for i in range(4)],
        ),
    )
    binding = dict(
        implementation_id="original_math_implementation",
        point_id="actual_point",
        task_plan_id=plan["id"],
        original_class_source="frozen_numerics",
    )
    protocol = publish(
        source / "protocol/record.json",
        dict(
            schema="v35_bounded_whole_task_protocol.v1",
            task_binding=binding,
            task_plan=entry(source / "task_plan/record.json"),
        ),
    )
    deadline = time.time() + 3600
    publish(
        source / "execution_window/record.json",
        dict(
            protocol_id=protocol["id"],
            first_launch_epoch=deadline - 4 * 3600,
            deadline_epoch=deadline,
        ),
    )
    publish(source / "queue/run_intent/record.json", dict(pid=123, birth="original"))
    for stage in recovery.STAGES:
        directory = source / stage
        publish(
            directory / "launch/record.json",
            dict(
                protocol_id=protocol["id"],
                stage=stage,
                global_deadline_epoch=deadline,
                pid=100 + recovery.STAGES.index(stage),
                birth="original",
            ),
        )
        successful = stage == "shard00"
        publish(
            directory / "exit/record.json",
            dict(
                protocol_id=protocol["id"],
                stage=stage,
                global_deadline_epoch=deadline,
                returncode=0 if successful else 1,
                stop_requested=True,
            ),
        )
        rows = [
            observation(1, "before_model_load", deadline=deadline),
            observation(2, "after_model_load.after_cleanup", deadline=deadline),
            observation(
                3,
                "shard_complete.after_cleanup" if successful else "class_row_end",
                deadline=deadline,
                stopped=not successful,
            ),
        ]
        for index, row in enumerate(rows):
            publish(
                directory / "resources" / f"event{index:06d}/record.json",
                dict(protocol_id=protocol["id"], stage=stage, observation=row),
            )
        host = dict(
            rss_limit_bytes=recovery.HOST_LIMIT,
            available_reserve_bytes=recovery.HOST_RESERVE,
            max_observed_peak_rss_bytes=5 * recovery.GIB,
            min_observed_available_bytes=100 * recovery.GIB,
            all_passed=successful,
        )
        if successful:
            publish(
                directory / "result/record.json",
                dict(
                    protocol_id=protocol["id"],
                    stage=stage,
                    status="COMPLETE",
                    model_released=True,
                    resources=dict(observations=rows, host=host),
                    **zeros(),
                ),
            )
        else:
            gpu_only = [
                {
                    k: v
                    for k, v in row.items()
                    if k not in {"host", "deadline_epoch", "deadline_pass"}
                }
                for row in rows
            ]
            publish(
                directory / "failure/record.json",
                dict(
                    protocol_id=protocol["id"],
                    stage=stage,
                    error_type="TailStopRequested",
                    completed_task_caches_preserved=True,
                    current_uncommitted_task_not_checkpoint=True,
                    automatic_retry=False,
                    variant_fallback=False,
                    host_resources=host,
                    resources=dict(
                        observations=gpu_only,
                        limits=rows[0]["limits"],
                        peak_reset_calls=0,
                        all_passed=False,
                        max_observed_peak_allocated_bytes=1536,
                        min_boundary_free_bytes=3 * recovery.GIB,
                    ),
                    **zeros(),
                ),
            )
    publish(
        source / "host_resources/event000000/record.json",
        dict(
            protocol_id=protocol["id"],
            passed=True,
            reserve_bytes=recovery.HOST_RESERVE,
            available_bytes=100 * recovery.GIB,
            processes=[],
        ),
    )
    task_refs = []
    for task in plan["tasks"]:
        if task["task_id"] not in complete:
            continue
        directory = source / "task_cache" / f"task{task['index']:04d}"
        directory.mkdir(parents=True)
        gradient = (task["task_id"] + " durable CPU gradient fixture").encode()
        (directory / "gradient.pt").write_bytes(gradient)
        publish(
            directory / "record.json",
            dict(
                schema="v35_complete_task_gradient.v1",
                binding=binding,
                binding_sha256=cache_module.digest(binding),
                task_plan_id=plan["id"],
                task=task,
                parameter_spec=plan["parameter_spec"],
                complete_task=True,
                gradient_bytes=len(gradient),
                gradient_sha256=hashlib.sha256(gradient).hexdigest(),
                receipt=dict(
                    state_unchanged=True,
                    pre_state_identity="unchanged",
                    post_state_identity="unchanged",
                    original_class_bytecode_unchanged=True,
                    stage=recovery.STAGES[task["shard"]],
                    **zeros(),
                ),
            ),
        )
        task_refs.append(dict(task_id=task["task_id"], **entry(directory / "record.json")))
    coverage = dict(
        task_plan_id=plan["id"],
        binding_sha256=cache_module.digest(binding),
        complete_task_count=5,
        total_task_count=8,
        complete_task_ids=complete,
        missing_task_ids=missing,
        task_records=task_refs,
    )
    publish(
        source / "failure/record.json",
        dict(
            schema="v35_bounded_task_failure.v1",
            protocol_id=protocol["id"],
            error_type="ValueError",
            error="live worker RSS unavailable",
            stop_error=None,
            task_cache_coverage=coverage,
            no_automatic_retry=True,
            no_implicit_fallback=True,
            original_B_resume_authorized=False,
        ),
    )
    status = dict(
        phase="STOPPED_FAILURE_NO_RETRY",
        protocol_id=protocol["id"],
        error_type="ValueError",
        error="live worker RSS unavailable",
        active_children=[],
        global_deadline_epoch=deadline,
        original_B_resume_authorized=False,
    )
    (source / "queue/status.json").write_text(json.dumps(status))

    def check_result(p, stage, result, frozen_plan):
        assert p == protocol and frozen_plan == plan
        assert stage == "shard00" and result["status"] == "COMPLETE"

    control = SimpleNamespace(
        checked=checked,
        publish=publish,
        read_ref=read_ref,
        entry=entry,
        digest=cache_module.digest,
        now=lambda: "CPU_FIXTURE_ONLY",
        birth=lambda _pid: None,
        checked_protocol=lambda root: checked(Path(root) / "protocol/record.json"),
        check_result=check_result,
    )
    return SimpleNamespace(
        source=source,
        target=target,
        control=control,
        protocol=protocol,
        plan=plan,
        binding=binding,
        deadline=deadline,
    )


def run(f):
    return recovery.prepare_cache(
        f.source, f.target, f.control, expected_completed=5, expected_missing=3
    )


def rewrite(path, change):
    value = checked(path)
    value.pop("id")
    change(value)
    publish(path, value)


def test_import_copies_original_bytes_to_distinct_inodes_preserves_failed_source(fixture):
    f = fixture
    originals = {str(path): path.read_bytes() for path in f.source.rglob("*") if path.is_file()}
    receipt = run(f)
    assert receipt["complete_task_count"] == 5 and receipt["missing_task_count"] == 3
    assert receipt["remaining_rows"] == 6 and receipt["deadline_epoch"] == f.deadline
    assert receipt["new_execution_seconds_authorized"] == 0
    assert set(receipt["inherited_completed_stages"]) == {"shard00"}
    assert receipt["inherited_completed_stages"]["shard00"]["result"] == entry(
        f.source / "shard00/result/record.json"
    )
    assert (
        not receipt["original_failure_reclassified"] and not receipt["original_B_resume_authorized"]
    )
    assert receipt["original_math_binding_unchanged"]
    assert receipt["task_binding_sha256"] == cache_module.digest(f.binding)
    for item in receipt["task_records"]:
        source = Path(item["source_gradient"]["path"])
        target = Path(item["destination_gradient"]["path"])
        assert source.read_bytes() == target.read_bytes()
        assert (source.stat().st_dev, source.stat().st_ino) != (
            target.stat().st_dev,
            target.stat().st_ino,
        )
        assert checked(item["destination_record"]["path"])["binding"] == f.binding
    assert all(Path(path).read_bytes() == value for path, value in originals.items())
    first = receipt["task_records"][0]
    Path(first["destination_gradient"]["path"]).write_bytes(b"destination mutation fixture")
    assert (
        Path(first["source_gradient"]["path"]).read_bytes()
        == originals[first["source_gradient"]["path"]]
    )
    with pytest.raises(ValueError, match="overwrite"):
        run(f)


def test_gradient_corruption_rejected_during_copy_without_completed_receipt(fixture):
    path = fixture.source / "task_cache/task0000/gradient.pt"
    path.write_bytes(path.read_bytes() + b"corrupted")
    with pytest.raises(ValueError, match="checksum/length"):
        run(fixture)
    assert not (fixture.target / "task_cache/task0000").exists()
    assert not (fixture.target / "cache_inheritance/record.json").exists()


def test_known_signal_guard_failure_allowed_only_with_real_successful_shard00_exit(fixture):
    path = fixture.source / "failure/record.json"
    rewrite(
        path,
        lambda value: value.update(
            stop_error=copy.deepcopy(recovery.KNOWN_EXITED_SHARD00_GUARD_ERROR)
        ),
    )
    receipt = run(fixture)
    assert receipt["source_secondary_stop_guard_error"] == recovery.KNOWN_EXITED_SHARD00_GUARD_ERROR
    assert not receipt["original_failure_reclassified"]


@pytest.mark.parametrize("change", ["shard01", "signal9", "different_error", "nonzero_exit"])
def test_unknown_or_unverified_secondary_signal_guard_failure_rejected(fixture, change):
    secondary = copy.deepcopy(recovery.KNOWN_EXITED_SHARD00_GUARD_ERROR)
    if change == "shard01":
        secondary["error"] = secondary["error"].replace("shard00", "shard01")
    elif change == "signal9":
        secondary["error"] = secondary["error"].replace("'signal': 15", "'signal': 9")
    elif change == "different_error":
        secondary["error_type"] = "RuntimeError"
    else:
        rewrite(
            fixture.source / "shard00/exit/record.json", lambda value: value.update(returncode=1)
        )
    rewrite(
        fixture.source / "failure/record.json", lambda value: value.update(stop_error=secondary)
    )
    with pytest.raises(ValueError, match="stopped RSS|successful exit"):
        run(fixture)
    assert not (fixture.target / "task_cache").exists()


@pytest.mark.parametrize(
    "field,value",
    [
        ("allocated_pass", False),
        ("peak_allocated_bytes", 77 * recovery.GIB),
        ("free_bytes", 1),
        ("deadline_pass", False),
    ],
)
def test_failed_old_resource_gate_cannot_be_treated_as_stop_only(fixture, field, value):
    path = fixture.source / "shard01/resources/event000002/record.json"
    rewrite(path, lambda event: event["observation"].update({field: value}))
    with pytest.raises(ValueError, match="resource gate|deadline gate"):
        run(fixture)
    assert not (fixture.target / "task_cache").exists()


def test_old_host_overflow_rejected_even_with_true_pass_flag(fixture):
    path = fixture.source / "shard02/resources/event000001/record.json"
    rewrite(
        path, lambda event: event["observation"]["host"].update(peak_rss_bytes=161 * recovery.GIB)
    )
    with pytest.raises(ValueError, match="host resource gate"):
        run(fixture)


def test_non_stop_prior_worker_failure_not_recoverable_under_this_scope(fixture):
    path = fixture.source / "shard02/failure/record.json"
    rewrite(path, lambda value: value.update(error_type="OutOfMemoryError"))
    with pytest.raises(ValueError, match="externally stopped"):
        run(fixture)


def test_live_old_process_or_preexisting_coordinator_refuses_recovery(fixture):
    fixture.control.birth = lambda _pid: "original"
    with pytest.raises(ValueError, match="still alive"):
        run(fixture)
    fixture.control.birth = lambda _pid: None
    publish(fixture.source / "coordinator/attempt/record.json", dict(attempt=True))
    with pytest.raises(ValueError, match="already dispatched"):
        run(fixture)


def test_changed_record_or_new_unsealed_task_cannot_be_recomputed_silently(fixture):
    path = fixture.source / "task_cache/task0000/record.json"
    rewrite(path, lambda value: value["binding"].update(point_id="different"))
    with pytest.raises(ValueError, match="sealed failure coverage"):
        run(fixture)


def test_uncommitted_directory_refuses_resume_from_partial_task(fixture):
    (fixture.source / "task_cache/task0003").mkdir()
    with pytest.raises(ValueError, match="unsealed or partial"):
        run(fixture)


def test_original_absolute_deadline_is_not_renewed(fixture, monkeypatch):
    monkeypatch.setattr(recovery.time, "time", lambda: fixture.deadline + 1)
    with pytest.raises(ValueError, match="execution window"):
        run(fixture)
    assert not (fixture.target / "task_cache").exists()


def test_default_production_counts_reject_fixture_scope(fixture):
    with pytest.raises(ValueError, match="authorized recovery scope"):
        recovery.prepare_cache(fixture.source, fixture.target, fixture.control)
