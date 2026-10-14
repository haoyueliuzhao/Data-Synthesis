"""CPU-only passive handoff integration, phase leases, ownership and budgets."""

import importlib
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest

sys.path.insert(0, str(Path(__file__).parents[1] / "scripts"))
subject = importlib.import_module("finqa_v42_controller")


def test_runtime_and_historical_verifiers_are_isolated():
    assert subject.parent is not subject.verifier.parent
    assert subject.parent is not subject.base.verifier.parent
    assert subject.parent.ContextRunner is subject.ContextRunner
    assert subject.parent.LeasePool is subject.LeasePool
    assert subject.base.checked_protocol is subject.checked_protocol
    assert subject.verifier.parent.checked_protocol is not subject.checked_protocol
    assert subject.verifier.parent.MINIMUM_FREE_MIB == 73728
    assert subject.verifier.verifier.parent.ALLOWED_GPUS == (3, 4, 5, 7)
    assert len(subject.FILES) == 6
    assert subject.parent.RESOURCE_WAIT_SECONDS == 129600
    assert subject.verifier.parent.RESOURCE_WAIT_SECONDS == 86400


@pytest.fixture
def plan(tmp_path):
    return dict(
        id="new",
        output_root=str(tmp_path),
        allowed_gpu_indices=list(subject.ALLOWED_GPUS),
        gpu_uuids=subject.admission.GPU_UUIDS,
        cpu_affinity=subject.admission.CPU_AFFINITY,
    )


def device(plan, gpu=7, free=32 * 1024):
    return dict(
        index=gpu, uuid=plan["gpu_uuids"][str(gpu)], free_mib=free, processes=[dict(pid=12345)]
    )


def test_shared_device_phase_threshold_and_historical_result_scope(plan):
    row = device(plan)
    assert subject.eligible(row, plan, "train", {})
    assert subject.eligible(row, plan, "shard00", {})
    assert not subject.eligible(row, plan, "replay_R3", {})
    assert not subject.verifier.eligible(row, plan)
    with pytest.raises(ValueError, match="actual protocol owner"):
        subject.check_result(dict(plan, allowed_gpu_indices=[3, 4, 5]), "train", dict(gpu_index=7))


def test_gpu6_withdrawal_stops_future_dispatch_only(plan):
    row = device(plan, gpu=6)
    assert subject.eligible(row, plan, "distribution", {})
    subject.publish(
        Path(plan["output_root"]) / "queue/gpu6_withdrawal/record.json",
        dict(protocol_id="new", gpu_index=6, stop_future_dispatch=True),
    )
    assert not subject.eligible(row, plan, "distribution", {})


def test_total_four_slots_include_initializing_and_draining(monkeypatch):
    pool = subject.LeasePool(SimpleNamespace())
    pool.leases = {gpu: object() for gpu in (0, 1, 2, 6)}
    monkeypatch.setattr(subject.parent, "inventory", lambda: pytest.fail("no fifth slot"))
    assert pool.try_acquire(object(), "distribution") is None


def test_lease_uses_stage_context_two_real_checks_and_same_shared_namespace(
    plan, tmp_path, monkeypatch
):
    row = device(plan, gpu=5, free=35 * 1024)
    calls = []
    monkeypatch.setattr(subject.parent, "inventory", lambda: calls.append(True) or [row])
    monkeypatch.setattr(subject.parent, "host_memory", lambda: dict(available_bytes=1024**4))
    monkeypatch.setattr(subject.parent, "TRAINING_ROOT", tmp_path / "training")
    controller = SimpleNamespace(protocol=plan, disk_gate=lambda _: None)
    pool = subject.LeasePool(controller)
    runner = SimpleNamespace(
        context=dict(id="point", feedback=dict(mode="first_sampling")), disk_projection=lambda _: 0
    )
    acquired = pool.try_acquire(runner, "virtual_point")
    assert acquired[0] is row and len(calls) == 2
    lease = acquired[1]
    assert lease.gpu == 5 and pool.leases[5] is lease
    assert Path(lease.lock.name).name == "gpu-" + subject.parent.digest(row["uuid"]) + ".lock"
    lease.close()
    assert pool.leases == {}
    assert pool.try_acquire(runner, "replay_R3") is None


def test_post_lock_memory_race_releases_lease(plan, tmp_path, monkeypatch):
    good, low = device(plan, gpu=5), device(plan, gpu=5, free=31 * 1024)
    values = iter([[good], [low]])
    monkeypatch.setattr(subject.parent, "inventory", lambda: next(values))
    monkeypatch.setattr(subject.parent, "host_memory", lambda: dict(available_bytes=1024**4))
    monkeypatch.setattr(subject.parent, "TRAINING_ROOT", tmp_path / "training")
    pool = subject.LeasePool(SimpleNamespace(protocol=plan, disk_gate=lambda _: None))
    assert (
        pool.try_acquire(SimpleNamespace(context={}, disk_projection=lambda _: 0), "train") is None
    )
    assert not pool.leases


def test_host_ram_gate_unchanged(plan, monkeypatch):
    monkeypatch.setattr(subject.parent, "host_memory", lambda: dict(available_bytes=287 * 1024**3))
    monkeypatch.setattr(subject.parent, "inventory", lambda: pytest.fail("host first"))
    pool = subject.LeasePool(SimpleNamespace(protocol=plan))
    assert pool.try_acquire(object(), "train") is None


@pytest.fixture
def frontier(tmp_path, monkeypatch, plan):
    control = subject.Controller.__new__(subject.Controller)
    control.root, control.protocol = tmp_path, plan
    control.runs, control.active_coordinate = [], {}
    control._frontier_installed = False
    control.pilot_accepted = True
    control.resource_wait_used = 12345
    control.has_draining = lambda: False
    values, rows = {}, []
    for seed, arm, step, key in [(251, "C-only", 1192, "C251"), (389, "Full", 298, "Full389")]:
        values[key] = dict(
            id=key,
            seed=seed,
            arm=arm,
            step=step,
            due_outer=True,
            task_plan=key + "plan",
            feedback=dict(mode="first_sampling"),
        )
        values[key + "plan"] = {}
        bindings = {}
        for stage in (*subject.parent.SHARDS, "virtual_point", "replay_R3"):
            owner = "V38" if key == "C251" and stage == "shard02" else "V40"
            values[owner] = dict(id=owner)
            result_ref, exit_ref = key + stage, key + stage + "exit"
            values[result_ref] = dict(protocol_id=owner, stage=stage)
            values[exit_ref] = dict(returncode=0, stop_requested=False)
            bindings[stage] = dict(
                protocol_scope="parent",
                protocol_ref=owner,
                protocol_id=owner,
                result=result_ref,
                exit=exit_ref,
            )
        for stage in ("distribution", "train"):
            bindings[stage] = dict(protocol_scope="current")
        rows.append(
            dict(
                original_context=key,
                new_context_directory=str(tmp_path / key),
                origin_context_directory=str(tmp_path / "old" / key),
                inherited_compute_seconds=7777,
                phase_deadlines_epoch={"class_gradients": 1500},
                stage_bindings=bindings,
            )
        )
    control.inherited = dict(context_inheritances=rows)
    checks, enqueues = [], []
    monkeypatch.setattr(subject, "read_ref", lambda ref: values[ref])
    monkeypatch.setattr(subject.parent, "read_ref", lambda ref: values[ref])
    monkeypatch.setattr(
        subject.inheritance,
        "resolve_origin_context",
        lambda directory, protocol: tmp_path / "old" / directory.name,
    )
    monkeypatch.setattr(
        subject, "check_result", lambda p, s, r, task: checks.append((p["id"], s, r["protocol_id"]))
    )
    monkeypatch.setattr(subject.ContextRunner, "update", lambda *a, **kw: None)
    control.enqueue_remaining = lambda: enqueues.append(True)
    control.disk_gate = lambda _: None
    return SimpleNamespace(
        control=control, values=values, rows=rows, checks=checks, enqueues=enqueues
    )


def test_frontier_inherits_each_actual_stage_owner_and_never_repeats_pilot(frontier):
    f = frontier
    assert f.control.create_context(subject.parent.FIRST, pilot=True) is None
    assert f.control.pilot_accepted and len(f.control.runs) == 2
    assert all(
        run.pending() == ["distribution"] and run.compute_used == 7777 for run in f.control.runs
    )
    assert ("V38", "shard02", "V38") in f.checks
    assert ("V40", "replay_R3", "V40") in f.checks
    assert len(f.enqueues) == 1
    with pytest.raises(ValueError, match="one installation"):
        f.control.create_context(subject.parent.FIRST, pilot=True)


def test_registered_partial_class_restores_only_completed_stages(frontier):
    frontier.rows[0]["stage_bindings"]["shard00"] = dict(protocol_scope="current")
    frontier.control.create_context(subject.parent.FIRST, pilot=True)
    run = frontier.control.runs[0]
    assert run.pending() == ["shard00"]
    assert "shard00" not in run.results and "shard00" not in run.dispatched


def test_nonzero_parent_exit_cannot_be_inherited(frontier):
    frontier.values["C251shard00exit"]["returncode"] = 1
    with pytest.raises(ValueError, match="actual exit"):
        frontier.control.create_context(subject.parent.FIRST, pilot=True)


def test_inherited_deadline_and_compute_not_reset(frontier, monkeypatch):
    frontier.control.create_context(subject.parent.FIRST, pilot=True)
    run = frontier.control.runs[0]
    run.inherited["phase_deadlines_epoch"]["distribution"] = 2000
    monkeypatch.setattr(subject.time, "time", lambda: 1500)
    assert run.stage_limit("distribution") == ("distribution", 500)
    assert run.compute_used == 7777
    monkeypatch.setattr(subject.time, "time", lambda: 2000)
    with pytest.raises(subject.DurablePause, match="inherited phase deadline"):
        run.stage_limit("distribution")


def test_launch_absolute_deadline_not_double_charged(frontier, monkeypatch):
    frontier.control.create_context(subject.parent.FIRST, pilot=True)
    run = frontier.control.runs[0]
    run.inherited["phase_deadlines_epoch"]["distribution"] = 2000
    run.phase_started["distribution"] = 1
    run._lifecycle_launch_gate = lambda: None
    monkeypatch.setattr(subject.time, "time", lambda: 1500)
    monkeypatch.setattr(subject.time, "monotonic", lambda: 100)
    monkeypatch.setattr(subject, "birth", lambda _: "born")
    monkeypatch.setattr(subject.parent, "worker_environment", lambda _: {})
    commands = []
    monkeypatch.setattr(
        subject.subprocess,
        "Popen",
        lambda command, **kw: commands.append(command) or SimpleNamespace(pid=4444),
    )
    run.launch("distribution", device(run.protocol, gpu=7), object())
    launch = run.active["distribution"]["launch"]
    assert launch["deadline_epoch"] == 2000
    assert launch["minimum_free_mib"] == 24 * 1024
    assert launch["actual_dispatch_inventory"]["processes"] == [dict(pid=12345)]
    assert str(frontier.control.root / "implementation/finqa_v42_worker.py") in commands[0]
    assert run.active["distribution"]["stage_deadline_monotonic"] == 600


@pytest.fixture
def wait_state(tmp_path, monkeypatch, plan):
    control = subject.Controller.__new__(subject.Controller)
    control.protocol = plan
    control._last_wait_sequences, control._worker_wait_intervals, control._pre_cuda_waiters = (
        {},
        {},
        {},
    )
    control._idle_wait_intervals = [(3, 6)]
    control.inherited = dict(inherited_resource_wait_seconds=100)
    runner = SimpleNamespace(root=tmp_path, context=dict(id="endpoint"))
    launch = dict(
        stage="generate",
        pid=4444,
        birth="born",
        gpu_index=7,
        gpu_uuid=plan["gpu_uuids"]["7"],
        deadline_epoch=1000,
    )
    item = dict(launch=launch, started_monotonic=1, process=SimpleNamespace(poll=lambda: None))
    monkeypatch.setattr(subject.time, "monotonic", lambda: 20)

    def write(where, start, end, **extra):
        body = dict(
            schema="v39_pre_cuda_admission.v1",
            protocol_id="new",
            context_id="endpoint",
            **launch,
            cuda_initialized=False,
            phase="READY",
            sequence=0,
            observed_monotonic=end,
            waiting_started_monotonic=start,
            waiting_finished_monotonic=end,
            waiting_seconds=end - start,
            memory_phase="generate",
            minimum_free_mib=48 * 1024,
            gpu_admission_policy_schema=subject.admission.POLICY_SCHEMA,
        )
        body.update(extra)
        path = tmp_path / "generate" / where / "pre_cuda_wait/status.json"
        subject.publish(path, body)
        return path

    return SimpleNamespace(control=control, runner=runner, item=item, write=write)


def test_endpoint_nested_waits_union_accounted_without_sequence_collision(wait_state):
    f = wait_state
    f.write(".", 2, 5)
    f.write("pre_cuda_rechecks/check0001", 4, 10)
    f.write("pre_cuda_rechecks/check0002", 10, 12)
    f.control.capture_wait(f.runner, "generate", f.item)
    f.control.recount_resource_wait()
    assert len(f.control._worker_wait_intervals) == 3
    assert f.control.resource_wait_used == 110
    f.control.capture_wait(f.runner, "generate", f.item)
    f.control.recount_resource_wait()
    assert f.control.resource_wait_used == 110


@pytest.mark.parametrize(
    "extra",
    [
        {"minimum_free_mib": 73728},
        {"pid": 5555},
        {"cuda_initialized": True},
        {"deadline_epoch": 1001},
    ],
)
def test_admission_heartbeat_identity_policy_deadline_fail_closed(wait_state, extra):
    f = wait_state
    f.write(".", 2, 5, **extra)
    with pytest.raises(ValueError, match="actual worker/phase"):
        f.control.capture_wait(f.runner, "generate", f.item)


def test_unregistered_third_endpoint_recheck_forbidden(wait_state):
    wait_state.write("pre_cuda_rechecks/check0003", 2, 5)
    with pytest.raises(ValueError, match="unregistered endpoint"):
        wait_state.control.capture_wait(wait_state.runner, "generate", wait_state.item)


def test_distribution_only_explicit_coordinate_gets_new_window(frontier, monkeypatch):
    f = frontier
    f.values["C251"].update(seed=251, arm="Full", step=894)
    f.rows[0]["phase_deadline_overrides"] = dict(
        distribution=dict(
            window_seconds=7200,
            starts_at_first_dispatch=True,
            only_authorized_coordinate=[251, "Full", 894],
        )
    )
    f.rows[0]["phase_deadlines_epoch"]["distribution"] = 100
    f.control.create_context(subject.parent.FIRST, pilot=True)
    run = f.control.runs[0]
    monkeypatch.setattr(subject.time, "time", lambda: 1500)
    assert run.stage_limit("distribution") == ("distribution", 7200)
    run.context["seed"] = 389
    with pytest.raises(ValueError, match="exception scope"):
        run.stage_limit("distribution")


def test_distribution_window_is_single_dispatch_and_old_outer_is_retained(frontier, monkeypatch):
    f = frontier
    f.values["C251"].update(seed=251, arm="Full", step=894)
    f.rows[0]["phase_deadline_overrides"] = dict(
        distribution=dict(
            window_seconds=7200,
            starts_at_first_dispatch=True,
            only_authorized_coordinate=[251, "Full", 894],
        )
    )
    f.rows[0]["phase_deadlines_epoch"]["distribution"] = 100
    f.rows[0]["inherited_compute_seconds"] = 45784
    f.control.protocol["authorization"] = {"approved": True}
    f.control.create_context(subject.parent.FIRST, pilot=True)
    run = f.control.runs[0]
    run._lifecycle_launch_gate = lambda: None
    monkeypatch.setattr(subject.time, "time", lambda: 1500)
    monkeypatch.setattr(subject.time, "monotonic", lambda: 100)
    monkeypatch.setattr(subject, "birth", lambda _: "born")
    monkeypatch.setattr(subject.parent, "worker_environment", lambda _: {})
    monkeypatch.setattr(subject.subprocess, "Popen", lambda *a, **k: SimpleNamespace(pid=4444))
    run.launch("distribution", device(run.protocol), object())
    window = subject.checked(run.root / "distribution_recovery_window/record.json")
    assert window["started_epoch"] == 1500
    assert window["deadline_epoch"] == 8700
    assert window["original_deadline_epoch"] == 100
    assert window["inherited_outer_used_seconds"] == 45784
    assert run.compute_used == 45784
    with pytest.raises(ValueError, match="unregistered next"):
        run.launch("distribution", device(run.protocol), object())


@pytest.mark.parametrize("usage,allowed", [(93466, True), (129599, True), (129600, False)])
def test_cumulative_36hour_gate_does_not_reset_previous_usage(usage, allowed):
    control = subject.Controller.__new__(subject.Controller)
    control.resource_wait_used = usage
    if allowed:
        control.resource_wait_gate()
    else:
        with pytest.raises(subject.DurablePause):
            control.resource_wait_gate()
    assert control.resource_wait_used == usage


def test_initialization_wall_is_added_to_93466_not_zero(tmp_path, monkeypatch):
    root = tmp_path / "episode"
    control = subject.Controller.__new__(subject.Controller)
    control.root, control.protocol = root, dict(id="new")
    control.inherited = dict(inherited_resource_wait_seconds=93466)
    control._original_inherited_wait, control._registered_at = 93466, 1000
    monkeypatch.setattr(subject, "__file__", str(root / "implementation" / subject.FILES[0]))
    monkeypatch.setattr(subject.time, "time", lambda: 1100.4)
    monkeypatch.setattr(subject, "own_command", lambda: ["CPU-test"])
    monkeypatch.setattr(subject, "birth", lambda _: "born")
    monkeypatch.setattr(subject.parent.Controller, "run", lambda self: "CPU-only")
    assert control.run() == "CPU-only"
    launch = subject.checked(root / "launch_01/record.json")
    assert launch["inherited_global_wait_at_dispatch"] == 93567
    assert launch["inherited_resource_wait_before_initialization"] == 93466
    assert control.resource_wait_used == 93567
    assert launch["accepted_pilot_repeated"] is False
    with pytest.raises(FileExistsError):
        control.run()


@pytest.mark.parametrize(
    "changed", [None, "new_feedback_episodes", "explicitly_reexecuted_unreturned_requests"]
)
def test_recovered_feedback_result_preserves_real_dose(monkeypatch, changed):
    monkeypatch.setattr(subject, "_original_check_result", lambda *args: None)
    item = dict(
        original_context_id="point",
        seed=389,
        arm="C-only",
        step=894,
        feedback_resume=dict(id="binding"),
    )
    monkeypatch.setattr(subject, "read_ref", lambda _: dict(context_inheritances=[item]))
    plan = dict(schema="v42_explicit_bounded_same_point_recovery_protocol.v1", inheritance={})
    result = dict(
        context_id="point",
        feedback_resume_binding_id="binding",
        inherited_feedback_episodes=450,
        new_feedback_episodes=250,
        first_time_feedback_episodes=249,
        explicitly_reexecuted_unreturned_requests=1,
        scoring_calls=700,
        class_gradient_passes=0,
        virtual_point_recomputations=0,
        old_unreturned_request_outcome_remains_unknown=True,
    )
    if changed:
        result[changed] += 1
        with pytest.raises(ValueError, match="completion dose changed"):
            subject.check_result(plan, "virtual_point", result)
    else:
        subject.check_result(plan, "virtual_point", result)


def test_recovered_virtual_lifecycle_admits_250_without_forging_700(monkeypatch):
    run = subject.ContextRunner.__new__(subject.ContextRunner)
    run.context = dict(
        id="context", seed=389, arm="C-only", step=894, feedback=dict(mode="first_sampling")
    )
    run.inherited = dict(feedback_resume=dict(original_context_id="context", point_id="point"))
    run.active = dict(virtual_point=dict(launch=dict(gpu_index=4, gpu_uuid="GPU-real")))
    run.protocol, run.task_plan = dict(id="new"), {}
    checks = []
    monkeypatch.setattr(subject, "check_result", lambda *args: checks.append(args[2].copy()))
    result = dict(
        context_id="context",
        point_id="point",
        gpu_index=4,
        gpu_uuid="GPU-real",
        feedback_mode="first_sampling",
        response_count=500,
        new_feedback_episodes=250,
        memory_phase="virtual_first_sampling",
        minimum_free_mib=32 * 1024,
        gpu_admission_policy_schema=subject.admission.POLICY_SCHEMA,
    )
    run.lifecycle_result_validator("virtual_point", result)
    assert checks[0]["new_feedback_episodes"] == result["new_feedback_episodes"] == 250
    result["gpu_uuid"] = "GPU-wrong"
    with pytest.raises(ValueError, match="identity/device/point"):
        run.lifecycle_result_validator("virtual_point", result)
