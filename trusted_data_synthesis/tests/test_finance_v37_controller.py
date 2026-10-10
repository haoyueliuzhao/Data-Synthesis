"""CPU-only V37 shared leases, scientific scope and pilot/budget wiring."""

import importlib
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest

sys.path.insert(0, str(Path(__file__).parents[1] / "scripts"))
queue = importlib.import_module("finqa_v37_controller")


def protocol():
    return dict(
        id="protocol",
        gpu_uuids={str(i): f"GPU-{i}" for i in queue.ALLOWED_GPUS},
        cpu_affinity={str(i): "0-3" for i in queue.ALLOWED_GPUS},
    )


def task_plan():
    return dict(
        assignments=[dict(shard=i, task_ids=[f"task{i}"]) for i in range(4)],
        tasks=[dict(task_id=f"task{i}", state_ids=["z"]) for i in range(4)],
    )


class Clock:
    current = 1000.0

    def monotonic(self):
        return self.current

    def time(self):
        return 1_800_000_000 + self.current

    def sleep(self, seconds):
        self.current += seconds


@pytest.fixture
def pool(tmp_path, monkeypatch):
    manager = queue.Controller.__new__(queue.Controller)
    manager.root, manager.protocol = tmp_path, protocol()
    manager.runs = []
    manager.stop = False
    manager.draining_episode = None
    manager.draining_episode_count = 0
    manager.resource_wait_used = 0.0
    manager._resource_waiting = False
    manager._resource_accounting_at = 1000.0
    manager.pilot_accepted = False
    manager.completed_arms = {(137, "Static"), (251, "Static")}
    manager.completed_evaluations = set(manager.completed_arms)
    manager.active_coordinate = {}
    manager.latest = {}
    manager.accepted_new_updates = manager.accepted_new_outers = 0
    manager.disk_gate = lambda _: None
    manager.pool = queue.LeasePool(manager)
    clock = Clock()
    monkeypatch.setattr(queue, "time", clock)
    monkeypatch.setattr(queue._v36.lifecycle, "time", clock)
    monkeypatch.setattr(queue, "TRAINING_ROOT", tmp_path / "original_training")
    monkeypatch.setattr(queue, "host_memory", lambda: dict(available_bytes=1000 * queue.GIB))
    monkeypatch.setattr(queue, "process_memory", lambda _: dict(rss_bytes=0, peak_rss_bytes=0))
    monkeypatch.setattr(
        queue,
        "inventory",
        lambda: [
            dict(index=i, uuid=f"GPU-{i}", free_mib=80 * 1024, processes=[])
            for i in queue.ALLOWED_GPUS
        ],
    )
    return manager, clock


def make_runner(manager, *, seed=137, arm="C-only", step=1192, due=True):
    root = manager.root / f"ctx{len(manager.runs)}"
    queue.publish(root / "plan/record.json", task_plan())
    context = dict(
        id=f"ctx{len(manager.runs)}",
        seed=seed,
        arm=arm,
        step=step,
        due_outer=due,
        task_plan=queue.entry(root / "plan/record.json"),
        feedback=dict(mode="sealed_existing", expected_point_id="point"),
        branch=dict(contribution_only=arm == "C-only", b_N=0.0 if arm == "C-only" else 0.2),
        outer_done=[298, 596, 894],
        parameter_spec=[dict(name="p", shape=[2], dtype="torch.float32")],
    )
    runner = queue.ContextRunner(manager, root, context)
    manager.runs.append(runner)
    return runner


def resources(stage):
    rows = []
    for label in ("after_model_load.after_cleanup", "model_released.after_cleanup"):
        rows.append(
            dict(
                label=label,
                boundary=True,
                allocated_bytes=1024,
                reserved_bytes=2048,
                peak_allocated_bytes=1536,
                peak_reserved_bytes=2048,
                free_bytes=3 * queue.GIB,
                total_bytes=80 * queue.GIB,
                passed=True,
                allocated_pass=True,
                free_pass=True,
                stop_requested=False,
                deadline_pass=True,
                limits=dict(
                    allocated_memory_limit_bytes=queue.MAXIMUM_ALLOCATED_BYTES,
                    free_memory_reserve_bytes=queue.MINIMUM_DEVICE_FREE_BYTES,
                ),
                host=dict(
                    rss_bytes=queue.GIB,
                    peak_rss_bytes=2 * queue.GIB,
                    available_bytes=100 * queue.GIB,
                    passed=True,
                    rss_pass=True,
                    available_pass=True,
                    rss_limit_bytes=queue.stage_rss_limit(stage),
                    available_reserve_bytes=96 * queue.GIB,
                ),
            )
        )
    return dict(
        all_gates_passed=True,
        limits_unchanged=True,
        maximum_allocated_bytes=queue.MAXIMUM_ALLOCATED_BYTES,
        minimum_device_free_bytes=queue.MINIMUM_DEVICE_FREE_BYTES,
        peak_resets_before_model_load=1,
        peak_resets_after_model_loading_begins=0,
        helper_peak_reset_calls=0,
        observations=rows,
        observed_peak_allocated_bytes=1536,
        observed_minimum_boundary_free_bytes=3 * queue.GIB,
        host=dict(
            all_passed=True,
            rss_limit_bytes=queue.stage_rss_limit(stage),
            available_reserve_bytes=96 * queue.GIB,
            max_observed_peak_rss_bytes=2 * queue.GIB,
            min_observed_available_bytes=100 * queue.GIB,
        ),
    )


def result(stage="shard00"):
    body = dict(
        protocol_id="protocol",
        context_id="ctx0",
        stage=stage,
        status="COMPLETE",
        model_released=True,
        gpu_index=4,
        gpu_uuid="GPU-4",
        API_calls=0,
        new_sampling_calls=0,
        scoring_calls=0,
        optimizer_steps=0,
        replayed_responses=0,
        model_optimizer_rng_buffers_unchanged=True,
        resources=resources(stage),
    )
    if stage in queue.SHARDS:
        body.update(
            task_ids=task_plan()["assignments"][queue.SHARDS.index(stage)]["task_ids"],
            task_count=1,
            class_task_calls=1,
            reused_task_ids=[],
        )
    else:
        body["denominator"] = 700
    return body


def test_new_production_contract_does_not_reuse_reference_deadline_or_performance_gate():
    assert queue.OUTER_COMPUTE_SECONDS == 24 * 3600
    assert queue.STAGE_LIMITS["replay_R3"] == 16 * 3600
    assert queue.ALLOWED_GPUS == (3, 4, 5, 7)
    assert queue.FIRST == (137, "C-only")
    assert queue.INITIAL_STEPS[(137, "C-only")] == 1192


def test_four_logical_shards_can_start_on_three_idle_registered_gpus(pool, monkeypatch):
    manager, _ = pool
    runner = make_runner(manager)
    rows = [
        dict(index=i, uuid=f"GPU-{i}", free_mib=80 * 1024, processes=[]) for i in queue.ALLOWED_GPUS
    ]
    rows[0].update(free_mib=52 * 1024, processes=[dict(pid=99999)])
    monkeypatch.setattr(queue, "inventory", lambda: rows)
    acquired = [manager.pool.try_acquire(runner, stage) for stage in queue.SHARDS[:3]]
    assert [value[0]["index"] for value in acquired] == [4, 5, 7]
    assert manager.pool.try_acquire(runner, "shard03") is None
    first = acquired[0][1]
    assert Path(first.lock.name).parent == queue.TRAINING_ROOT / "locks"
    assert Path(first.lock.name).name == "gpu-" + queue.digest("GPU-4") + ".lock"
    first.close()
    last = manager.pool.try_acquire(runner, "shard03")
    assert last[0]["index"] == 4
    for _, lease in [*acquired[1:], last]:
        lease.close()


def test_one_global_four_worker_cap_across_contexts_and_cpu_initialization(pool):
    manager, _ = pool
    first, second = make_runner(manager), make_runner(manager, seed=251)
    leases = [manager.pool.try_acquire(first, s) for s in queue.SHARDS]
    assert len(manager.pool.leases) == 4  # Reservations count even before Popen/CPU loading.
    assert manager.pool.try_acquire(second, "shard00") is None
    for _, lease in leases:
        lease.close()


def test_host_admission_accounts_for_unconsumed_active_worker_envelopes(pool, monkeypatch):
    manager, _ = pool
    runner = make_runner(manager)
    _, lease = manager.pool.try_acquire(runner, "shard00")
    monkeypatch.setattr(queue, "host_memory", lambda: dict(available_bytes=400 * queue.GIB))
    assert (
        manager.pool.try_acquire(runner, "shard01") is None
    )  # 160 existing +160 next +96 reserve.
    lease.close()


def test_draining_blocks_fourth_shard_as_a_wait_not_as_an_error(pool):
    manager, _ = pool
    runner = make_runner(manager)
    runner.dispatched = {"shard00", "shard01", "shard02"}
    runner.active["shard00"] = dict(lifecycle_state="RESULT_COMMITTED_DRAINING")
    assert runner.pending() == []
    del runner.active["shard00"]
    runner.results["shard00"] = {}
    assert runner.pending() == ["shard03"]


def test_contexts_share_one_draining_episode_deadline_and_keep_global_dispatch_closed(pool):
    manager, clock = pool
    first, second = make_runner(manager), make_runner(manager, seed=251)
    for pid, runner in enumerate((first, second), 100):
        runner.active["shard00"] = dict(
            lifecycle_state="RUNNING", launch=dict(pid=pid, birth=str(pid))
        )
    first._lifecycle_enter_draining("shard00", first.active["shard00"], ({}, dict(id="first")))
    clock.current += 100
    second._lifecycle_enter_draining("shard00", second.active["shard00"], ({}, dict(id="second")))
    assert (
        first._lifecycle_episode["deadline_monotonic"]
        == second._lifecycle_episode["deadline_monotonic"]
        == 1600
    )
    assert first.pending() == second.pending() == []
    first.active.clear()
    first._lifecycle_close_episode()
    assert manager.draining_episode is not None
    second.active.clear()
    second._lifecycle_close_episode()
    assert manager.draining_episode is None


def test_shard_result_accepts_dynamic_physical_gpu_without_old_reference_eight_comparisons():
    value = result()
    assert queue.check_result(protocol(), "shard00", value, task_plan()) is value
    assert "comparison" not in value


@pytest.mark.parametrize(
    "key,value",
    [
        ("API_calls", 1),
        ("optimizer_steps", 1),
        ("replayed_responses", 1),
        ("new_sampling_calls", 1),
        ("gpu_index", 0),
        ("class_task_calls", True),
        ("model_optimizer_rng_buffers_unchanged", False),
    ],
)
def test_unregistered_scientific_work_or_device_or_state_mutation_is_rejected(key, value):
    measured = result()
    measured[key] = value
    with pytest.raises(ValueError):
        queue.check_result(protocol(), "shard00", measured, task_plan())


@pytest.mark.parametrize("stage", ["shard00", "replay_R3", "train", "generate"])
def test_cold_process_memory_and_host_limits_remain_strict(stage):
    measured = resources(stage)
    queue.check_resources(measured, stage)
    measured["observations"][-1]["peak_allocated_bytes"] = 77 * queue.GIB
    with pytest.raises(ValueError):
        queue.check_resources(measured, stage)


def test_existing_feedback_gate_refuses_new_point_resampling_or_rescoring(pool):
    manager, _ = pool
    runner = make_runner(manager)
    runner.active["virtual_point"] = dict(launch=dict(gpu_index=4, gpu_uuid="GPU-4"))
    measured = dict(
        context_id=runner.context["id"],
        gpu_index=4,
        gpu_uuid="GPU-4",
        feedback_mode="sealed_existing",
        response_count=500,
        point_id="point",
        new_feedback_episodes=0,
        new_sampling_calls=0,
        scoring_calls=0,
    )
    runner.lifecycle_result_validator("virtual_point", measured)
    for changes in (dict(point_id="new"), dict(new_feedback_episodes=700), dict(scoring_calls=700)):
        with pytest.raises(ValueError):
            runner.lifecycle_result_validator("virtual_point", {**measured, **changes})


def test_full_distribution_cannot_silently_become_contribution_only(pool):
    manager, _ = pool
    runner = make_runner(manager, arm="Full")
    runner.active["distribution"] = dict(launch=dict(gpu_index=4, gpu_uuid="GPU-4"))
    runner.results["virtual_point"] = dict(point_id="full-point")
    measured = dict(
        context_id=runner.context["id"],
        gpu_index=4,
        gpu_uuid="GPU-4",
        denominator=700,
        contribution_only=False,
        b_N=0.2,
        point_id="full-point",
        C_N_pi_saved=True,
        outer_commits=0,
        reference_comparison_performed=False,
    )
    runner.lifecycle_result_validator("distribution", measured)
    with pytest.raises(ValueError):
        runner.lifecycle_result_validator(
            "distribution", {**measured, "contribution_only": True, "b_N": 0.0}
        )


def test_remaining_matrix_never_enqueues_before_real_pilot_acceptance(pool):
    manager, _ = pool
    manager.create_context = lambda *_: pytest.fail("cannot unlock remaining matrix")
    manager.create_evaluation = lambda *_: pytest.fail("cannot dispatch endpoint generation")
    manager.enqueue_remaining()


def test_nonpilot_or_wrong_next_step_cannot_unlock_matrix(pool):
    manager, _ = pool
    runner = make_runner(manager, arm="Full")
    runner.finished = True
    runner.results["train"] = dict(
        next_checkpoint="saved",
        actual_optimizer_steps=1,
        outer_committed=True,
        initial_step=1192,
        committed_step=1193,
        endpoint_complete=False,
    )
    manager.active_coordinate[(137, "Full")] = runner
    with pytest.raises(ValueError, match="pilot"):
        manager.accept_finished(runner)
    assert manager.pilot_accepted is False


def test_normal_queueing_behind_owned_work_does_not_consume_external_idle_budget(pool):
    manager, clock = pool
    manager._resource_waiting = False
    clock.current += 25 * 3600
    manager.account_resource_wait()
    assert manager.resource_wait_used == 0
    manager._resource_waiting = True
    clock.current += 35
    manager.account_resource_wait()
    assert manager.resource_wait_used == 35  # Once for the whole pool, not multiplied by contexts.


def test_replay_disk_projection_uses_actual_response_count_and_every16_checkpoint(pool):
    manager, _ = pool
    runner = make_runner(manager)
    runner.results["virtual_point"] = dict(response_count=573)
    expected = (36 + 2) * (2 * 8 + 4 * 1024**2)
    assert runner.disk_projection("replay_R3") == expected


def test_disk_low_water_pauses_without_deleting_or_retrying(pool, monkeypatch):
    manager, _ = pool
    manager.checkpoint_size = 30 * 1024**2
    monkeypatch.setattr(queue.shutil, "disk_usage", lambda _: SimpleNamespace(free=32 * queue.GIB))
    with pytest.raises(queue.DurablePause, match="no deletion authorized"):
        queue.Controller.disk_gate(manager, 1)


def test_generate_command_contains_stage_for_unchanged_lifecycle_ownership_guard(pool, monkeypatch):
    manager, _ = pool
    context = dict(id="evaluation:389:full", seed=389, arm="Full", due_outer=False)
    runner = queue.ContextRunner(manager, manager.root / "evaluation", context, evaluation=True)
    manager.runs.append(runner)
    process = SimpleNamespace(pid=1001, poll=lambda: None)
    calls = []
    monkeypatch.setattr(
        queue.subprocess, "Popen", lambda command, **kwargs: calls.append(command) or process
    )
    monkeypatch.setattr(queue, "birth", lambda _: "born")
    lease = SimpleNamespace(close=lambda: None)
    runner.launch("generate", dict(index=7, uuid="GPU-7"), lease)
    command = calls[0]
    assert command[command.index("--stage") + 1] == "generate"
    assert command[command.index("--arm") + 1] == "full"
