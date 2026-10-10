"""CPU-only strict result, parallel ownership and ONE global-clock tests."""

import copy
import importlib
import signal
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parents[1] / "scripts"))
queue = importlib.import_module("finqa_v35_task_controller")


def protocol():
    return dict(
        id="p",
        gpu_uuids={str(i): f"GPU-{i}" for i in queue.ALLOWED_GPUS},
        cpu_affinity={str(i): "0-3" for i in queue.ALLOWED_GPUS},
    )


def plan():
    return dict(
        task_ids=["a", "b", "c", "d"],
        tasks=[dict(task_id=t, state_ids=["z"]) for t in "abcd"],
        parameter_spec=[dict(name="p", shape=[2], dtype="torch.float32")],
        assignments=[dict(shard=i, task_ids=[t]) for i, t in enumerate("abcd")],
    )


def production_scope():
    tasks = []
    package_index = 0
    for index in range(744):
        packages = []
        for _ in range(4 if index < 236 else 3):
            packages.append(dict(row_count=3 if package_index < 38 else 2))
            package_index += 1
        tasks.append(
            dict(
                index=index,
                task_id=f"task{index:04d}",
                shard=index % 4,
                state_ids=["a", "b"] if index < 616 else ["a"],
                packages=packages,
                row_count=sum(package["row_count"] for package in packages),
            )
        )
    assignments = []
    for shard in range(4):
        selected = [task for task in tasks if task["shard"] == shard]
        assignments.append(
            dict(
                shard=shard,
                task_ids=[task["task_id"] for task in selected],
                task_indices=[task["index"] for task in selected],
                row_count=sum(task["row_count"] for task in selected),
            )
        )
    return dict(
        tasks=tasks,
        task_ids=[task["task_id"] for task in tasks],
        shards=4,
        assignments=assignments,
        package_count=2468,
        row_count=4974,
        state_count=1360,
        parameter_spec=[
            dict(name=f"parameter{i}", shape=[1], dtype="torch.float32") for i in range(112)
        ],
    )


def test_exact_full_production_task_package_row_parameter_scope():
    source = production_scope()
    assert queue.check_task_scope(source) is source


@pytest.mark.parametrize(
    "key,value",
    [
        ("package_count", 2467),
        ("row_count", 4973),
        ("state_count", 1359),
        ("shards", 3),
    ],
)
def test_production_counts_are_strict(key, value):
    source = production_scope()
    source[key] = value
    with pytest.raises(ValueError):
        queue.check_task_scope(source)


def test_shard_missing_duplicated_reordered_task_or_partial_coverage_is_rejected():
    for kind in ("missing", "duplicate", "reorder", "shard_count"):
        source = production_scope()
        tasks = source["assignments"][0]["task_ids"]
        if kind == "missing":
            tasks.pop()
        elif kind == "duplicate":
            tasks[-1] = tasks[0]
        elif kind == "reorder":
            tasks.reverse()
        else:
            source["assignments"].pop()
        with pytest.raises(ValueError):
            queue.check_task_scope(source)


def test_production_parameter_coordinates_must_be_112_unique_fp32():
    for kind in ("missing", "duplicate", "dtype"):
        source = production_scope()
        specs = source["parameter_spec"]
        if kind == "missing":
            specs.pop()
        elif kind == "duplicate":
            specs[-1] = specs[0]
        else:
            specs[0]["dtype"] = "torch.float64"
        with pytest.raises(ValueError, match="112 ordered FP32"):
            queue.check_task_scope(source)


def row(index):
    return dict(index=index, uuid=f"GPU-{index}", processes=[], free_mib=80 * 1024)


def observation(label, coordinator=False):
    limit = (192 if coordinator else 160) * queue.GIB
    return dict(
        label=label,
        boundary=True,
        allocated_bytes=1024,
        reserved_bytes=2048,
        peak_allocated_bytes=1536,
        peak_reserved_bytes=2048,
        free_bytes=3 * queue.GIB,
        total_bytes=80 * queue.GIB,
        limits=dict(
            allocated_memory_limit_bytes=queue.MAXIMUM_ALLOCATED_BYTES,
            free_memory_reserve_bytes=queue.MINIMUM_DEVICE_FREE_BYTES,
        ),
        allocated_pass=True,
        free_pass=True,
        stop_requested=False,
        passed=True,
        deadline_pass=True,
        host=dict(
            rss_bytes=10 * queue.GIB,
            peak_rss_bytes=11 * queue.GIB,
            available_bytes=100 * queue.GIB,
            rss_limit_bytes=limit,
            available_reserve_bytes=96 * queue.GIB,
            rss_pass=True,
            available_pass=True,
            passed=True,
        ),
    )


def result(stage="coordinator"):
    coordinator = stage == "coordinator"
    gpu = queue.STAGE_GPU[stage]
    value = dict(
        protocol_id="p",
        stage=stage,
        gpu_index=gpu,
        gpu_uuid=f"GPU-{gpu}",
        status="COMPLETE",
        backend_version=queue.BACKEND_VERSION,
        original_B_resume_authorized=False,
        API_calls=0,
        new_sampling_calls=0,
        scoring_calls=0,
        optimizer_steps=0,
        replayed_responses=0,
        class_gradient_passes=0,
        resources=dict(
            all_gates_passed=True,
            limits_unchanged=True,
            maximum_allocated_bytes=queue.MAXIMUM_ALLOCATED_BYTES,
            minimum_device_free_bytes=queue.MINIMUM_DEVICE_FREE_BYTES,
            observed_peak_allocated_bytes=1536,
            observed_minimum_boundary_free_bytes=3 * queue.GIB,
            peak_resets_before_model_load=1,
            peak_resets_after_model_loading_begins=0,
            helper_peak_reset_calls=0,
            observations=[
                observation(label, coordinator)
                for label in (
                    "after_model_load.after_cleanup",
                    "after_distribution.after_cleanup"
                    if coordinator
                    else "shard_complete.after_cleanup",
                )
            ],
            host=dict(
                rss_limit_bytes=(192 if coordinator else 160) * queue.GIB,
                available_reserve_bytes=96 * queue.GIB,
                max_observed_peak_rss_bytes=11 * queue.GIB,
                min_observed_available_bytes=100 * queue.GIB,
                all_passed=True,
            ),
        ),
    )
    if coordinator:
        value.update(
            numeric_pass=True,
            comparison=dict.fromkeys(queue.COHORT_COMPARISON_KEYS, True),
            global_class_gradient_passes=1,
            reused_completed_responses=573,
            task_count=744,
            state_count=1360,
        )
    else:
        value.update(
            task_ids=plan()["assignments"][queue.SHARD_STAGES.index(stage)]["task_ids"],
            task_count=1,
            global_class_gradient_pass_contribution=True,
            class_task_calls=1,
            reused_task_ids=[],
            model_optimizer_rng_buffers_existing_grad_unchanged=True,
        )
    return value


@pytest.mark.parametrize("stage", queue.STAGES)
def test_complete_exact_shards_and_coordinator_are_accepted_without_mutating_telemetry(stage):
    value = result(stage)
    before = copy.deepcopy(value)
    assert queue.check_result(protocol(), stage, value, plan()) is value
    assert value == before


@pytest.mark.parametrize(
    "key,value",
    [
        ("API_calls", 1),
        ("new_sampling_calls", 1),
        ("scoring_calls", 1),
        ("optimizer_steps", 1),
        ("replayed_responses", 1),
        ("replayed_responses", False),
        ("class_gradient_passes", 1),
        ("class_gradient_passes", False),
        ("global_class_gradient_passes", 2),
        ("global_class_gradient_passes", True),
        ("reused_completed_responses", 572),
        ("task_count", 743),
        ("state_count", 1359),
        ("status", "PARTIAL"),
        ("numeric_pass", False),
        ("gpu_index", 3),
        ("gpu_uuid", "wrong"),
        ("original_B_resume_authorized", True),
    ],
)
def test_scope_expansion_partial_result_and_foreign_device_are_rejected(key, value):
    measured = result()
    measured[key] = value
    with pytest.raises(ValueError):
        queue.check_result(protocol(), "coordinator", measured, plan())


@pytest.mark.parametrize("key", queue.COHORT_COMPARISON_KEYS)
def test_all_eight_comparisons_remain_strict(key):
    measured = result()
    measured["comparison"][key] = False
    with pytest.raises(ValueError, match="comparisons"):
        queue.check_result(protocol(), "coordinator", measured, plan())


def test_failed_additional_comparison_cannot_be_hidden():
    measured = result()
    measured["comparison"]["extra"] = False
    with pytest.raises(ValueError, match="comparisons"):
        queue.check_result(protocol(), "coordinator", measured, plan())


@pytest.mark.parametrize(
    "key,value",
    [
        ("task_ids", ["d"]),
        ("task_count", 0),
        ("task_count", True),
        ("global_class_gradient_pass_contribution", False),
        ("model_optimizer_rng_buffers_existing_grad_unchanged", False),
        ("class_task_calls", 2),
        ("class_task_calls", True),
        ("reused_task_ids", ["a"]),
    ],
)
def test_shard_requires_exact_whole_task_ownership_and_state_identity(key, value):
    measured = result("shard00")
    measured[key] = value
    with pytest.raises(ValueError):
        queue.check_result(protocol(), "shard00", measured, plan())


@pytest.mark.parametrize(
    "key,value",
    [
        ("peak_allocated_bytes", 77 * queue.GIB),
        ("free_bytes", queue.GIB),
        ("allocated_pass", False),
        ("free_pass", False),
        ("passed", False),
        ("stop_requested", True),
        ("deadline_pass", False),
    ],
)
def test_memory_values_and_deadline_flags_remain_hard_gates(key, value):
    measured = result()
    measured["resources"]["observations"][0][key] = value
    with pytest.raises(ValueError):
        queue.check_result(protocol(), "coordinator", measured, plan())


@pytest.mark.parametrize(
    "key,value",
    [
        ("rss_limit_bytes", 193 * queue.GIB),
        ("peak_rss_bytes", 193 * queue.GIB),
        ("available_bytes", 95 * queue.GIB),
        ("available_reserve_bytes", 95 * queue.GIB),
        ("rss_pass", False),
        ("available_pass", False),
        ("passed", False),
    ],
)
def test_host_observation_cannot_relax_rss_or_available_reserve(key, value):
    measured = result()
    measured["resources"]["observations"][0]["host"][key] = value
    with pytest.raises(ValueError):
        queue.check_result(protocol(), "coordinator", measured, plan())


class Clock:
    def __init__(self):
        self.current = 1000.0

    def monotonic(self):
        return self.current

    def time(self):
        return 1_800_000_000 + self.current

    def sleep(self, value):
        self.current += value


class Lock:
    def __init__(self):
        self.closed = False

    def close(self):
        self.closed = True


class Process:
    def __init__(self, pid, *, running=True):
        self.pid = pid
        self.code = None if running else 0

    def poll(self):
        return self.code

    def wait(self):
        assert self.code is not None
        return self.code


@pytest.fixture
def controller(tmp_path, monkeypatch):
    clock = Clock()
    monkeypatch.setattr(queue, "time", clock)
    current = queue.Controller.__new__(queue.Controller)
    current.root = tmp_path
    current.protocol = protocol()
    current.task_plan = plan()
    current.active, current.results = {}, {}
    current.wait_used, current.stop = 0.0, False
    current.deadline = current.deadline_epoch = current.first_launch_epoch = None
    current.host_event_count = 0
    monkeypatch.setattr(queue, "verify_original_B_paused", lambda _: None)
    monkeypatch.setattr(queue, "inventory", lambda: [row(i) for i in queue.ALLOWED_GPUS])
    monkeypatch.setattr(
        queue,
        "host_memory",
        lambda: dict(total_bytes=1024 * queue.GIB, available_bytes=800 * queue.GIB),
    )
    monkeypatch.setattr(queue, "birth", lambda pid: f"birth-{pid}")
    monkeypatch.setattr(queue, "disk_memory", lambda *_: dict(free_bytes=100, admission_bytes=99))
    return current, clock


def test_only_registered_empty_gpu_uuids_are_eligible():
    for index in (0, 1, 2, 6):
        assert not queue.eligible(row(index), protocol())
    for index in queue.ALLOWED_GPUS:
        assert queue.eligible(row(index), protocol())
    value = row(7)
    value["processes"] = [dict(pid=100)]
    assert not queue.eligible(value, protocol())
    value.update(processes=[], free_mib=queue.MINIMUM_FREE_MIB - 1)
    assert not queue.eligible(value, protocol())


def test_whole_four_gpu_admission_never_silently_downgrades_workers(controller, monkeypatch):
    current, clock = controller
    monkeypatch.setattr(queue, "host_memory", lambda: dict(available_bytes=735 * queue.GIB))
    monkeypatch.setattr(queue, "WAIT_BUDGET_SECONDS", 15)
    with pytest.raises(ValueError, match="24-hour"):
        current.acquire(queue.SHARD_STAGES)
    assert not current.active
    assert current.deadline is None
    assert current.wait_used == 15


def test_shared_deadline_counts_coordinator_resource_wait(controller, monkeypatch):
    current, clock = controller
    current.deadline = clock.current + 7
    current.deadline_epoch = clock.time() + 7
    monkeypatch.setattr(queue, "inventory", lambda: [])
    with pytest.raises(ValueError, match="shared global deadline"):
        current.acquire(("coordinator",))
    assert clock.current == 1007
    assert current.wait_used == 7


def test_cpu_initialization_counts_toward_four_workers_and_one_gpu(controller, monkeypatch):
    current, clock = controller
    processes = []

    def start(*args, **kwargs):
        process = Process(101 + len(processes))
        processes.append(process)
        return process

    monkeypatch.setattr(queue.subprocess, "Popen", start)
    for stage in queue.SHARD_STAGES:
        current.launch(stage, row(queue.STAGE_GPU[stage]), Lock())
    assert len(current.active) == 4
    assert current.deadline == 1000 + queue.GLOBAL_DEADLINE_SECONDS
    window = queue.checked(current.root / "execution_window/record.json")
    assert window["deadline_epoch"] == current.deadline_epoch
    with pytest.raises(ValueError, match="worker cap"):
        current.launch("coordinator", row(7), Lock())
    assert len(processes) == 4


def test_global_deadline_not_reset_when_coordinator_starts_after_shards_exit(
    controller, monkeypatch
):
    current, clock = controller
    processes = []

    def start(*args, **kwargs):
        process = Process(101 + len(processes))
        processes.append(process)
        return process

    monkeypatch.setattr(queue.subprocess, "Popen", start)
    current.launch("shard00", row(3), Lock())
    deadline, epoch = current.deadline, current.deadline_epoch
    processes[0].code = 0
    current.record_exit("shard00")
    clock.current += 800
    current.results = {stage: result(stage) for stage in queue.SHARD_STAGES}
    queue.publish(current.root / "complete_task_cache/record.json", dict(complete_task_count=744))
    current.launch("coordinator", row(7), Lock())
    assert current.deadline == deadline and current.deadline_epoch == epoch
    assert current.active["coordinator"]["launch"]["global_deadline_epoch"] == epoch


def test_live_shard_blocks_coordinator_even_on_different_gpu(controller, monkeypatch):
    current, clock = controller
    current.active["shard00"] = dict(
        process=Process(101),
        lock=Lock(),
        launch=dict(stage="shard00", pid=101, birth="birth-101", gpu_index=3, gpu_uuid="GPU-3"),
    )
    with pytest.raises(ValueError, match="cannot overlap"):
        current.launch("coordinator", row(7), Lock())


def test_missing_shard_or_cache_prevents_coordinator_even_without_live_process(controller):
    current, _ = controller
    with pytest.raises(ValueError, match="every shard exit"):
        current.launch("coordinator", row(7), Lock())
    current.results = {stage: result(stage) for stage in queue.SHARD_STAGES}
    with pytest.raises(ValueError, match="sealed complete-task coverage"):
        current.launch("coordinator", row(7), Lock())


def test_global_stop_sends_all_terms_then_all_kills_with_one_grace(controller, monkeypatch):
    current, clock = controller
    calls = []
    locks = []
    processes = {}
    for index, stage in enumerate(queue.SHARD_STAGES):
        process, lock = Process(index + 10), Lock()
        locks.append(lock)
        processes[process.pid] = process
        current.active[stage] = dict(
            process=process,
            lock=lock,
            launch=dict(
                stage=stage,
                pid=process.pid,
                birth=f"birth-{process.pid}",
                gpu_index=queue.STAGE_GPU[stage],
                gpu_uuid=f"GPU-{queue.STAGE_GPU[stage]}",
            ),
            started_monotonic=clock.current,
        )

    def send(launch, sig):
        calls.append((launch["pid"], sig, clock.current))
        if sig == signal.SIGKILL:
            processes[launch["pid"]].code = -9

    monkeypatch.setattr(queue, "signal_owned", send)
    monkeypatch.setattr(queue, "TERM_GRACE_SECONDS", 20)
    current.drain_stopped()
    assert [call[1] for call in calls] == [signal.SIGTERM] * 4 + [signal.SIGKILL] * 4
    assert {call[2] for call in calls[:4]} == {1000}
    assert {call[2] for call in calls[4:]} == {1020}
    assert clock.current <= 1021
    assert not current.active and all(lock.closed for lock in locks)


def test_parent_observed_host_failure_is_persisted_before_raising(controller, monkeypatch):
    current, clock = controller
    monkeypatch.setattr(queue, "host_memory", lambda: dict(available_bytes=95 * queue.GIB))
    with pytest.raises(ValueError, match="host RSS or MemAvailable"):
        current.observe_host()
    evidence = queue.checked(current.root / "host_resources/event000000/record.json")
    assert evidence["passed"] is False


def test_one_signal_guard_error_does_not_skip_other_workers(controller, monkeypatch):
    current, clock = controller
    calls = []
    for i, stage in enumerate(queue.SHARD_STAGES[:2]):
        current.active[stage] = dict(
            process=Process(i + 1),
            lock=Lock(),
            launch=dict(
                stage=stage,
                pid=i + 1,
                birth=f"birth-{i + 1}",
                gpu_index=queue.STAGE_GPU[stage],
                gpu_uuid=f"GPU-{queue.STAGE_GPU[stage]}",
            ),
            started_monotonic=clock.current,
        )
    first, second = [item["process"] for item in current.active.values()]

    def send(launch, sig):
        calls.append((launch["pid"], sig))
        if launch["pid"] == 1 and sig == signal.SIGTERM:
            raise ValueError("simulated identity guard refusal")
        (first if launch["pid"] == 1 else second).code = -int(sig)

    monkeypatch.setattr(queue, "signal_owned", send)
    monkeypatch.setattr(queue, "TERM_GRACE_SECONDS", 10)
    with pytest.raises(ValueError, match="signal guards failed"):
        current.drain_stopped()
    assert calls[:2] == [(1, signal.SIGTERM), (2, signal.SIGTERM)]
    assert (1, signal.SIGKILL) in calls
    assert not current.active


def test_post_popen_failure_keeps_owned_gpu_lock_for_global_stop(controller, monkeypatch):
    current, _ = controller
    lock = Lock()
    monkeypatch.setattr(current, "acquire", lambda _: ({3: row(3)}, {3: lock}))

    def broken_launch(stage, gpu, owned_lock):
        current.active[stage] = dict(
            process=Process(101), lock=owned_lock, launch=dict(stage=stage, gpu_index=3)
        )
        raise OSError("simulated durable launch publication failure")

    monkeypatch.setattr(current, "launch", broken_launch)
    with pytest.raises(OSError):
        current.run_group(("shard00",))
    assert not lock.closed
    assert current.active["shard00"]["lock"] is lock


def test_parent_host_gate_catches_worker_peak_rss(controller, monkeypatch):
    current, clock = controller
    current.active["shard00"] = dict(
        process=Process(101),
        lock=Lock(),
        launch=dict(stage="shard00", pid=101, birth="birth-101", gpu_index=3, gpu_uuid="GPU-3"),
    )
    monkeypatch.setattr(
        queue,
        "process_memory",
        lambda _: dict(rss_bytes=159 * queue.GIB, peak_rss_bytes=161 * queue.GIB),
    )
    with pytest.raises(ValueError, match="host RSS"):
        current.observe_host()


def test_disk_gate_uses_all_states_and_all_parameter_coordinates(tmp_path):
    observed = queue.disk_memory(tmp_path, plan())
    assert observed["estimated_class_tensor_bytes"] == 2 * 4 * 4
    assert observed["admission_bytes"] == 64 + 32 * queue.GIB


def test_insufficient_disk_stops_before_any_worker(controller, monkeypatch):
    current, _ = controller
    monkeypatch.setattr(queue, "disk_memory", lambda *_: dict(free_bytes=98, admission_bytes=99))
    with pytest.raises(ValueError, match="insufficient disk"):
        current.acquire(queue.SHARD_STAGES)
    assert not current.active and current.deadline is None


def test_original_source_protocol_is_read_only_and_remains_sealed():
    inherited = queue.inherited_protocol()
    assert inherited["id"] == queue.V34_PROTOCOL_ID
    assert inherited["original_B_resume_authorized"] is False
    assert len(queue._prior_manifest["sha256"]) == 16


def test_exit_accounting_records_actual_observed_lifetime_including_grace(controller, monkeypatch):
    current, clock = controller
    process = Process(101)
    monkeypatch.setattr(queue.subprocess, "Popen", lambda *args, **kwargs: process)
    current.launch("shard00", row(3), Lock())
    clock.current += queue.GLOBAL_DEADLINE_SECONDS + 50
    process.code = -15
    current.record_exit("shard00", stopped=True)
    exit_record = queue.checked(current.root / "shard00/exit/record.json")
    assert exit_record["elapsed_worker_wall_seconds"] == queue.GLOBAL_DEADLINE_SECONDS + 50
    accounting = current.worker_accounting()
    assert accounting["total_elapsed_worker_wall_seconds"] == queue.GLOBAL_DEADLINE_SECONDS + 50
    assert accounting["total_elapsed_worker_hours"] > 4
    assert accounting["active_worker_count"] == 0
    assert accounting["includes_CPU_initialization_and_shutdown_grace"] is True


def test_protocol_separates_scheduled_worker_hours_from_shared_shutdown_grace(tmp_path):
    for name in ("authorization", "audit", "task_plan"):
        queue.publish(tmp_path / name / "record.json", dict(scope=name))
    directory = tmp_path / "implementation"
    directory.mkdir()
    (directory / "finqa_v34_tail_memory.py").write_text("fixture")
    (directory / queue.FILES[2]).write_text("fixture")
    common = queue.checked(queue.V34_ROOT / "protocol/record.json")
    body = queue.protocol_body(
        common,
        dict(source_commit="a" * 40, id="implementation"),
        tmp_path,
        at="test",
        observed=[],
        task_binding={},
    )
    assert body["scheduled_worker_hours_upper_bound"] == 16
    assert body["shutdown_grace_seconds"] == 600
    assert body["shutdown_grace_worker_hours_upper_bound"] == 4 * 600 / 3600
    assert body["grace_does_not_authorize_new_tasks"] is True
    assert body["scheduled_worker_hours_excludes_shutdown_grace"] is True
    assert body["global_deadline_seconds"] == 4 * 3600
