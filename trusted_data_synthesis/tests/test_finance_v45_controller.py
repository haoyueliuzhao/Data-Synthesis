"""CPU-only passive handoff integration, phase leases, ownership and budgets."""

import importlib
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest

sys.path.insert(0, str(Path(__file__).parents[1] / "scripts"))
subject = importlib.import_module("finqa_v45_controller")


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
    assert subject.DISPATCH_ORDER == (5, 2, 0, 4, 3, 7, 1, 6)
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
        host_admission_policy=subject.admission.host_policy_record(),
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


def test_gpu5_then_gpu2_priority_respects_real_resource_eligibility(plan, tmp_path, monkeypatch):
    rows = [device(plan, gpu=gpu, free=64 * 1024) for gpu in (0, 2, 5)]
    monkeypatch.setattr(subject.parent, "inventory", lambda: rows)
    monkeypatch.setattr(subject.parent, "host_memory", lambda: dict(available_bytes=400 * 1024**3))
    monkeypatch.setattr(subject.parent, "TRAINING_ROOT", tmp_path / "training")
    pool = subject.LeasePool(SimpleNamespace(protocol=plan, disk_gate=lambda _: None))
    runner = SimpleNamespace(context={}, disk_projection=lambda _: 0)
    row, lease = pool.try_acquire(runner, "train")
    assert row["index"] == 5
    lease.close()
    rows[-1]["free_mib"] = 0
    row, lease = pool.try_acquire(runner, "train")
    assert row["index"] == 2
    lease.close()


def test_measured_host_admission_gate_keeps_reserve(plan, monkeypatch):
    monkeypatch.setattr(subject.parent, "host_memory", lambda: dict(available_bytes=143 * 1024**3))
    monkeypatch.setattr(subject.parent, "inventory", lambda: pytest.fail("host first"))
    pool = subject.LeasePool(SimpleNamespace(protocol=plan))
    assert pool.try_acquire(object(), "train") is None


def live_pool(plan, monkeypatch, *, stage="virtual_point", count=3, rss=22, peak=24):
    pool = subject.LeasePool(SimpleNamespace(protocol=plan))
    for gpu in range(count):
        pool.leases[gpu] = SimpleNamespace(
            stage=stage,
            gpu=gpu,
            runner=SimpleNamespace(active={stage: dict(launch=dict(pid=100 + gpu, birth="born"))}),
        )
    monkeypatch.setattr(subject, "birth", lambda _: "born")
    monkeypatch.setattr(
        subject.parent,
        "process_memory",
        lambda _: dict(
            rss_bytes=rss * 1024**3,
            peak_rss_bytes=peak * 1024**3,
        ),
    )
    monkeypatch.setattr(subject.parent, "host_memory", lambda: dict(available_bytes=400 * 1024**3))
    return pool


def test_actual_three_coordinator_observations_admit_class_without_old_full_cap(plan, monkeypatch):
    pool = live_pool(plan, monkeypatch)
    assert pool._host_admission("shard01")
    observation = pool.last_host_admission
    assert observation["needed_bytes"] == (96 + 160 + 3 * (64 - 22)) * 1024**3
    assert observation["decision"] == "ADMIT_HOST_MEMORY"
    assert len(observation["active"]) == 3
    assert all(row["birth"] == "born" and row["observed"] for row in observation["active"])
    assert subject.parent.HOST_RAM["reserve_bytes"] == 96 * 1024**3
    assert subject.parent.stage_rss_limit("train") == 192 * 1024**3
    assert subject.parent.stage_rss_limit("shard01") == 160 * 1024**3


def test_live_high_water_above_empirical_budget_increases_remaining_reservation(plan, monkeypatch):
    pool = live_pool(plan, monkeypatch, stage="train", count=1, rss=10, peak=80)
    assert pool._host_admission("distribution")
    assert pool.last_host_admission["needed_bytes"] == (96 + 64 + 112 - 10) * 1024**3


@pytest.mark.parametrize(
    "value",
    [
        None,
        {},
        [],
        dict(rss_bytes=None, peak_rss_bytes=None),
        dict(rss_bytes=True, peak_rss_bytes=2),
        dict(rss_bytes=3, peak_rss_bytes=2),
    ],
)
def test_missing_or_malformed_live_memory_waits_without_zero_fallback(plan, monkeypatch, value):
    pool = live_pool(plan, monkeypatch, count=1)
    monkeypatch.setattr(subject.parent, "process_memory", lambda _: value)
    assert not pool._host_admission("train")
    assert pool.last_host_admission["needed_bytes"] is None
    assert pool.last_host_admission["active"][0]["observed"] is False


@pytest.mark.parametrize("reader", ["birth", "process_memory"])
def test_proc_exit_observation_exception_only_blocks_new_dispatch(plan, monkeypatch, reader):
    pool = live_pool(plan, monkeypatch, count=1)

    def gone(_):
        raise ProcessLookupError("exiting")

    monkeypatch.setattr(subject if reader == "birth" else subject.parent, reader, gone)
    assert not pool._host_admission("train")
    assert pool.last_host_admission["observation_error"] == "ProcessLookupError"


def test_recycled_pid_or_disappearing_identity_never_counts_foreign_rss(plan, monkeypatch):
    pool = live_pool(plan, monkeypatch, count=1)
    answers = iter(["born", "replacement"])
    monkeypatch.setattr(subject, "birth", lambda _: next(answers))
    assert not pool._host_admission("train")
    assert not pool.last_host_admission["active"][0]["observed"]


@pytest.mark.parametrize("value", [None, True, -1, float("nan"), float("inf")])
def test_unusable_host_available_memory_waits_without_launch(plan, monkeypatch, value):
    pool = live_pool(plan, monkeypatch, count=0)
    monkeypatch.setattr(subject.parent, "host_memory", lambda: dict(available_bytes=value))
    assert not pool._host_admission("train")
    assert pool.last_host_admission["decision"] == "WAIT_FOR_HOST_MEMORY_OBSERVATION"


def test_invalid_helper_observation_is_never_compared_with_available(plan, monkeypatch):
    pool = live_pool(plan, monkeypatch, count=0)
    monkeypatch.setattr(subject.admission, "host_memory_requirement", lambda *args: None)
    assert not pool._host_admission("train")


def test_host_policy_evidence_is_verified_before_registration(monkeypatch):
    reference = dict(path="evidence", sha256="digest", id="identity")
    monkeypatch.setattr(
        subject.admission, "host_policy_record", lambda: dict(evidence_refs=[reference])
    )
    observed = []
    monkeypatch.setattr(subject, "read_ref", lambda ref: observed.append(ref))
    assert subject.host_policy_record()["evidence_refs"] == [reference]
    assert observed == [reference]
    monkeypatch.setattr(subject.admission, "host_policy_record", lambda: dict(evidence_refs=[]))
    with pytest.raises(ValueError, match="needs evidence"):
        subject.host_policy_record()


def test_unverified_old_migration_blocks_before_freeze_or_registration(tmp_path, monkeypatch):
    root = tmp_path / "new"
    monkeypatch.setattr(subject, "ROOT", root)

    def blocked():
        raise ValueError("old migration not stopped")

    monkeypatch.setattr(subject, "checked_supersession", blocked)
    monkeypatch.setattr(
        subject, "freeze", lambda *args: pytest.fail("must not create partial preparation")
    )
    with pytest.raises(ValueError, match="old migration not stopped"):
        subject.prepare(root, source_commit="commit")
    assert not root.exists()


@pytest.fixture
def frontier(tmp_path, monkeypatch, plan):
    control = subject.Controller.__new__(subject.Controller)
    control.root, control.protocol = tmp_path, plan
    control.pool = SimpleNamespace(last_host_admission={"decision": "ADMIT_HOST_MEMORY"})
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
    assert launch["actual_host_admission"] == {"decision": "ADMIT_HOST_MEMORY"}
    assert run.active["distribution"]["stage_deadline_monotonic"] is None
    assert "--deadline-epoch" not in commands[0]
    assert subject.DISPATCH_ORDER[:2] == (5, 2)


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
    control.pool = SimpleNamespace(last_host_admission=None)
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
    assert observed[0]["host_ram_admission_changed"] is True
    assert observed[0]["host_ram_runtime_hard_gates_unchanged"] is True
    assert observed[0]["last_host_admission"] is None
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


def test_generated_endpoint_command_passes_real_v45_cli_parser(frontier, monkeypatch):
    endpoint = importlib.import_module("finqa_v45_evaluation")
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
        index for index, arg in enumerate(command) if arg.endswith("finqa_v45_evaluation.py")
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
