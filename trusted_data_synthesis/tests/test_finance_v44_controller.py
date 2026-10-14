"""CPU-only passive handoff integration, phase leases, ownership and budgets."""

import importlib
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest

sys.path.insert(0, str(Path(__file__).parents[1] / "scripts"))
subject = importlib.import_module("finqa_v44_controller")


def test_runtime_and_historical_verifiers_are_isolated():
    assert subject.parent is not subject.verifier.parent
    assert subject.parent is not subject.base.verifier.parent
    assert subject.parent.ContextRunner is subject.ContextRunner
    assert subject.parent.LeasePool is subject.LeasePool
    assert subject.runtime.ROOT == subject.ROOT
    assert subject.verifier.ROOT == subject.PARENT_ROOT
    assert subject.base.checked_protocol is subject.checked_protocol
    assert subject.verifier.parent.checked_protocol is not subject.checked_protocol
    assert len(subject.FILES) == 7
    assert subject.MAX_GPU_WORKERS == 5
    assert subject.DISPATCH_ORDER == (0, 4, 5, 2, 3, 7, 1, 6)
    assert (
        subject.verifier.policy_record()["admission"][
            "maximum_total_workers_including_initializing_and_draining"
        ]
        == 4
    )
    assert (
        subject.policy_record()["admission"][
            "maximum_total_workers_including_initializing_and_draining"
        ]
        == 5
    )


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
    assert subject.verifier.eligible(row, plan, "train", {})
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


def test_total_five_slots_include_initializing_and_draining(monkeypatch):
    pool = subject.LeasePool(SimpleNamespace())
    pool.leases = {gpu: object() for gpu in (0, 1, 2, 4, 6)}
    monkeypatch.setattr(subject.parent, "inventory", lambda: pytest.fail("no sixth slot"))
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
    monkeypatch.setattr(subject.runtime, "read_ref", lambda ref: values[ref])
    monkeypatch.setattr(
        subject.inheritance,
        "resolve_origin_context",
        lambda directory, protocol: tmp_path / "old" / directory.name,
    )
    monkeypatch.setattr(
        subject, "check_result", lambda p, s, r, task: checks.append((p["id"], s, r["protocol_id"]))
    )
    monkeypatch.setattr(subject.ContextRunner, "update", lambda *a, **kw: None)
    monkeypatch.setattr(subject.runtime, "check_result", subject.check_result)
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


def test_expired_legacy_deadlines_are_accounting_only(frontier, monkeypatch):
    frontier.control.create_context(subject.parent.FIRST, pilot=True)
    run = frontier.control.runs[0]
    run.inherited["phase_deadlines_epoch"]["distribution"] = 100
    run.compute_used = 10**9
    run.controller.stop = False
    run.controller.resource_wait_used = 10**9
    monkeypatch.setattr(subject.time, "time", lambda: 1500)
    assert run.stage_limit("distribution") == ("distribution", None)
    run.time_gate()
    run.controller.stop = True
    with pytest.raises(subject.DurablePause, match="explicit safe stop"):
        run.time_gate()


def test_launch_passes_actual_none_and_no_deadline_argument(frontier, monkeypatch):
    frontier.control.create_context(subject.parent.FIRST, pilot=True)
    run = frontier.control.runs[0]
    run.inherited["phase_deadlines_epoch"]["distribution"] = 100
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
    run.launch("distribution", device(run.protocol), object())
    launch = run.active["distribution"]["launch"]
    assert launch["deadline_epoch"] is None
    assert run.active["distribution"]["stage_deadline_monotonic"] is None
    assert "--deadline-epoch" not in commands[0]
    assert subject.DISPATCH_ORDER[:2] == (0, 4)


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
        deadline_epoch=None,
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


def test_global_wait_is_not_a_gate_but_bad_accounting_is():
    control = subject.Controller.__new__(subject.Controller)
    control.resource_wait_used = 10**9
    control.resource_wait_gate()
    control.resource_wait_used = -1
    with pytest.raises(ValueError, match="accounting"):
        control.resource_wait_gate()


def test_fresh_attempt_paths_do_not_admit_parent_or_broad_paths():
    assert subject.allowed_root(subject.ROOT)
    assert subject.allowed_root(subject.ROOT / "attempts/attempt0002")
    assert not subject.allowed_root(subject.PARENT_ROOT)
    assert not subject.allowed_root(subject.ROOT / "attempts/attempt0001")
    assert not subject.allowed_root(subject.ROOT / "unexpected")


def test_completed_training_without_endpoint_seal_still_enqueues_generation():
    control = subject.Controller.__new__(subject.Controller)
    all_coordinates = {(seed, arm) for seed in subject.parent.SEEDS for arm in subject.parent.ARMS}
    control.pilot_accepted = True
    control.completed_arms = all_coordinates
    pending = (389, "Static")
    control.completed_evaluations = all_coordinates - {pending}
    control.active_coordinate, control.runs = {}, []
    generated = []
    control.create_evaluation = generated.append
    control.create_context = lambda _: pytest.fail("completed model must not retrain")
    control.enqueue_remaining()
    assert generated == [pending]


def status_controller(plan):
    control = subject.Controller.__new__(subject.Controller)
    control.root, control.protocol = Path(plan["output_root"]), plan
    control.runs = [
        SimpleNamespace(
            context=dict(id="point"),
            active={
                str(gpu): dict(
                    launch=dict(
                        stage="train",
                        pid=100 + gpu,
                        birth=str(gpu),
                        gpu_index=gpu,
                        gpu_uuid=plan["gpu_uuids"][str(gpu)],
                    ),
                    lifecycle_state="RESULT_COMMITTED_DRAINING" if gpu == 4 else "RUNNING",
                )
                for gpu in range(5)
            },
        )
    ]
    control._pre_cuda_waiters, control._admission_stop_errors = {}, []
    control.inherited = dict(inherited_resource_wait_seconds=100)
    control.pilot_accepted = True
    control.resource_wait_used = 120
    control.accepted_new_updates = control.accepted_new_outers = 0
    control.completed_arms = control.completed_evaluations = set()
    return control


def test_status_admits_five_including_draining_without_changing_historical_four(plan, monkeypatch):
    control = status_controller(plan)
    observed = []
    monkeypatch.setattr(subject, "status", lambda root, body: observed.append(body))
    control.update("RUNNING")
    assert len(observed[0]["active_children"]) == observed[0]["max_gpu_workers"] == 5
    assert observed[0]["host_ram_admission_unchanged"] is True
    with pytest.raises(ValueError, match="global worker/device cap"):
        subject.verifier.parent.Controller.update(control, "RUNNING")


def test_status_rejects_six_or_duplicate_gpu(plan, monkeypatch):
    control = status_controller(plan)
    monkeypatch.setattr(
        subject, "status", lambda *args: pytest.fail("invalid active set published")
    )
    control.runs[0].active["extra"] = dict(
        launch=dict(
            stage="train", pid=999, birth="999", gpu_index=5, gpu_uuid=plan["gpu_uuids"]["5"]
        )
    )
    with pytest.raises(ValueError, match="five-worker"):
        control.update("RUNNING")
    del control.runs[0].active["extra"]
    control.runs[0].active["4"]["launch"]["gpu_index"] = 0
    with pytest.raises(ValueError, match="five-worker"):
        control.update("RUNNING")


def test_generated_endpoint_command_passes_real_v44_cli_parser(frontier, monkeypatch):
    endpoint = importlib.import_module("finqa_v44_evaluation")
    f = frontier
    context = dict(id="evaluation:389:full", seed=389, arm="Full", due_outer=False)
    run = subject.ContextRunner(f.control, f.control.root / "eval", context, evaluation=True)
    run._lifecycle_launch_gate = lambda: None
    monkeypatch.setattr(subject, "birth", lambda _: "born")
    monkeypatch.setattr(subject.parent, "worker_environment", lambda _: {})
    commands = []
    monkeypatch.setattr(
        subject.subprocess,
        "Popen",
        lambda command, **kwargs: commands.append(command) or SimpleNamespace(pid=44),
    )
    calls = []
    monkeypatch.setattr(
        endpoint, "run", lambda *args: calls.append(args) or dict(status="COMPLETE", id="CPU")
    )
    run.launch("generate", device(f.control.protocol, gpu=5, free=48 * 1024), object())
    command = commands[0]
    script = next(
        index for index, arg in enumerate(command) if arg.endswith("finqa_v44_evaluation.py")
    )
    endpoint.main(command[script + 1 :])
    assert calls == [(f.control.root, 389, "full", 5, None)]
    monkeypatch.setattr(
        endpoint,
        "score",
        lambda root: calls.append(("score", root)) or dict(status="COMPLETE", id="CPU"),
    )
    endpoint.main(["score", "--root", str(f.control.root)])
    assert calls[-1] == ("score", f.control.root)
