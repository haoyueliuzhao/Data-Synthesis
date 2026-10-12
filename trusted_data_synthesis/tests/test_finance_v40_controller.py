"""CPU-only explicit recovery gate, inherited budget and observed-stop tests."""

import fcntl
import importlib
import sys
from contextlib import nullcontext
from pathlib import Path
from types import SimpleNamespace

import pytest

sys.path.insert(0, str(Path(__file__).parents[1] / "scripts"))
subject = importlib.import_module("finqa_v40_controller")


def test_only_isolated_runtime_changes_to_recovery_coordinate_and_eight_devices():
    assert subject.parent is not subject.verifier.parent
    assert subject.parent.FIRST == (389, "Full")
    assert subject.verifier.parent.FIRST == (137, "C-only")
    assert subject.ALLOWED_GPUS == tuple(range(8))
    assert subject.parent.ALLOWED_GPUS == (3, 4, 5, 7, 0, 1, 2, 6)
    assert subject.verifier.parent.ALLOWED_GPUS == (3, 4, 5, 7)
    assert subject.parent.ContextRunner is subject.ContextRunner
    assert subject.parent.checked_protocol is subject.checked_protocol
    assert subject.base.checked_protocol is subject.checked_protocol
    assert subject.verifier.parent.checked_protocol is not subject.checked_protocol
    assert len(subject.FILES) == 8


def test_global_worker_cap_remains_four(monkeypatch):
    pool = subject.parent.LeasePool(SimpleNamespace())
    pool.leases = {gpu: object() for gpu in (3, 4, 5, 6)}
    monkeypatch.setattr(subject.parent, "inventory", lambda: pytest.fail("fifth worker forbidden"))
    assert pool.try_acquire(object(), "train") is None


def test_new_gpu6_eligibility_does_not_change_historical_result_scope(tmp_path):
    plan = dict(
        id="new",
        output_root=str(tmp_path),
        gpu_uuids=subject.admission.GPU_UUIDS,
        allowed_gpu_indices=list(subject.ALLOWED_GPUS),
    )
    row = dict(index=6, uuid=plan["gpu_uuids"]["6"], free_mib=80000, processes=[])
    assert subject.eligible(row, plan)
    assert not subject.verifier.parent.eligible(row, plan)
    with pytest.raises(ValueError, match="actual protocol owner"):
        subject.check_result(
            dict(plan, allowed_gpu_indices=[3, 4, 5, 7]), "train", dict(gpu_index=6)
        )
    subject.publish(
        tmp_path / "queue/gpu6_withdrawal/record.json",
        dict(protocol_id="new", gpu_index=6, stop_future_dispatch=True),
    )
    assert not subject.eligible(row, plan)


@pytest.fixture
def frontier(monkeypatch, tmp_path):
    controller = subject.Controller.__new__(subject.Controller)
    controller.root = tmp_path / "new"
    controller.protocol = dict(id="new")
    controller.runs, controller.active_coordinate = [], {}
    controller.pilot_accepted = False
    controller._pilot_installed = controller._remaining_frontier_installed = False
    controller._pilot_context_id = None
    controller.resource_wait_used = 28088
    controller.has_draining = lambda: False
    values = {"old-plan": dict(id="old", allowed_gpu_indices=[3, 4, 5, 7])}
    items = []
    for seed, arm, step, key in ((389, "Full", 298, "pilot"), (251, "Full", 596, "other")):
        context = dict(
            id=key,
            seed=seed,
            arm=arm,
            step=step,
            due_outer=True,
            feedback=dict(mode="sealed_existing"),
            task_plan=key + "tasks",
        )
        values[key], values[key + "tasks"] = context, {}
        bindings = {}
        for stage in (*subject.parent.SHARDS, "virtual_point"):
            result = key + stage + "result"
            exited = key + stage + "exit"
            values[result] = dict(stage=stage, protocol_id="old", response_count=447)
            values[exited] = dict(returncode=0)
            bindings[stage] = dict(protocol_scope="parent", result=result, exit=exited)
        for stage in ("replay_R3", "distribution", "train"):
            bindings[stage] = dict(protocol_scope="current")
        item = dict(
            original_context=key,
            parent_protocol="old-plan",
            new_context_directory=str(tmp_path / "new" / key),
            origin_context_directory=str(tmp_path / "old" / key),
            stage_bindings=bindings,
            inherited_compute_seconds=44470,
            phase_deadlines_epoch={"class_gradients": 900, "replay_R3": 2000},
        )
        items.append(item)
    controller.inherited = dict(context_inheritances=items)
    checks, enqueues = [], []
    monkeypatch.setattr(subject, "read_ref", lambda ref: values[ref])
    monkeypatch.setattr(subject.parent, "read_ref", lambda ref: values[ref])
    monkeypatch.setattr(
        subject.inheritance,
        "resolve_origin_context",
        lambda directory, plan: tmp_path / "old" / directory.name,
    )
    monkeypatch.setattr(
        subject,
        "check_result",
        lambda plan, stage, result, task_plan: checks.append(
            (plan["id"], stage, result["protocol_id"])
        ),
    )
    monkeypatch.setattr(subject.ContextRunner, "update", lambda *a, **kw: None)
    monkeypatch.setattr(
        subject.parent.Controller, "enqueue_remaining", lambda self: enqueues.append(True)
    )
    return SimpleNamespace(
        controller=controller, values=values, checks=checks, items=items, enqueues=enqueues
    )


def test_only_failed_replay_pilot_is_installed_until_its_physical_exit(frontier):
    f = frontier
    runner = f.controller.create_context(subject.RECOVERY_COORDINATE, pilot=True)
    assert len(f.controller.runs) == 1 and runner.recovery_pilot
    assert runner.pending() == ["replay_R3"]
    assert runner.compute_used == 44470
    assert runner.dispatched == set(subject.parent.SHARDS) | {"virtual_point"}
    assert all(old == actual == "old" for old, _, actual in f.checks)
    f.controller.enqueue_remaining()
    assert len(f.controller.runs) == 1 and not f.enqueues
    with pytest.raises(ValueError, match="locked"):
        f.controller.create_context((251, "Full"))
    runner._lifecycle_launch_gate = lambda: None
    with pytest.raises(ValueError, match="unregistered next"):
        runner.launch("virtual_point", {}, None)


def test_remaining_parent_frontier_is_installed_once_after_pilot_gate(frontier):
    f = frontier
    f.controller.create_context(subject.RECOVERY_COORDINATE, pilot=True)
    f.controller.pilot_accepted = True
    f.controller.enqueue_remaining()
    f.controller.enqueue_remaining()
    assert [runner.context["id"] for runner in f.controller.runs] == ["pilot", "other"]
    assert f.controller._remaining_frontier_installed and len(f.enqueues) == 2


def test_recovery_phase_absolute_deadline_and_outer_consumption_are_not_reset(
    frontier, monkeypatch
):
    runner = frontier.controller.create_context(subject.RECOVERY_COORDINATE, pilot=True)
    monkeypatch.setattr(subject.time, "time", lambda: 1500)
    assert runner.stage_limit("replay_R3") == ("replay_R3", 500)
    assert runner.stage_limit("distribution") == ("distribution", 7200)
    assert runner.compute_used == 44470
    monkeypatch.setattr(subject.time, "time", lambda: 2000)
    with pytest.raises(subject.DurablePause, match="inherited phase deadline"):
        runner.stage_limit("replay_R3")


@pytest.mark.parametrize("mutation", ["new", "restored", "total", "alias"])
def test_replay_acceptance_preserves_restored_plus_actual_new_semantics(frontier, mutation):
    f = frontier
    runner = f.controller.create_context(subject.RECOVERY_COORDINATE, pilot=True)
    runner.active["replay_R3"] = dict(launch=dict(gpu_index=3, gpu_uuid="GPU-3"))
    f.values["final-checkpoint"] = {}
    result = dict(
        context_id="pilot",
        gpu_index=3,
        gpu_uuid="GPU-3",
        current_point_only=True,
        response_count=447,
        restored_completed_responses=261,
        replayed_responses=186,
        inherited_response_count=261,
        actual_new_response_calls=186,
        cumulative_complete_response_count=447,
        final_checkpoint="final-checkpoint",
    )
    runner.lifecycle_result_validator("replay_R3", result)
    if mutation == "new":
        result["replayed_responses"] = 447
    elif mutation == "restored":
        result["restored_completed_responses"] = 0
    elif mutation == "total":
        result["response_count"] = 700
    else:
        result["actual_new_response_calls"] = 447
    with pytest.raises(ValueError, match="completeness|remaining186"):
        runner.lifecycle_result_validator("replay_R3", result)


def test_train_validator_keeps_original_real_commit_check_then_exact_sft299_gate(
    frontier, monkeypatch
):
    runner = frontier.controller.create_context(subject.RECOVERY_COORDINATE, pilot=True)
    runner.active["train"] = dict(launch=dict(gpu_index=3, gpu_uuid="GPU-3"))
    commits = []
    monkeypatch.setattr(
        subject.parent,
        "validate_training_commit",
        lambda context, result: commits.append(result["committed_step"]),
    )
    result = dict(
        context_id="pilot",
        gpu_index=3,
        gpu_uuid="GPU-3",
        initial_step=298,
        committed_step=299,
        actual_optimizer_steps=1,
        optimizer_steps=1,
        outer_committed=True,
        registered_training_stop_step=299,
        execution_boundary_policy_protocol_id="new",
    )
    runner.lifecycle_result_validator("train", result)
    assert commits == [299]
    result.update(committed_step=596, actual_optimizer_steps=298, optimizer_steps=298)
    with pytest.raises(ValueError, match="SFT299"):
        runner.lifecycle_result_validator("train", result)
    assert commits == [299, 596]


def test_pilot_acceptance_requires_real_exit_before_unlock_and_preserves_counters(
    frontier, monkeypatch
):
    f = frontier
    runner = f.controller.create_context(subject.RECOVERY_COORDINATE, pilot=True)
    runner.finished, runner.reported_finished = True, False
    runner.results["train"] = dict(
        initial_step=298,
        committed_step=299,
        actual_optimizer_steps=1,
        outer_committed=True,
        next_checkpoint="next",
        outer_checkpoint="outer",
    )
    exited = dict(returncode=1, stop_requested=False, protocol_id="new", context_id="pilot")
    monkeypatch.setattr(subject, "checked", lambda path: exited)
    accepted = []

    def old_accept(controller, value):
        assert controller.pilot_accepted  # Bypass only obsolete hard-coded old pilot identity.
        controller.accepted_new_updates += value.results["train"]["actual_optimizer_steps"]
        controller.accepted_new_outers += 1
        accepted.append(value)

    f.controller.accepted_new_updates, f.controller.accepted_new_outers = 1667, 4
    monkeypatch.setattr(subject.parent.Controller, "accept_finished", old_accept)
    monkeypatch.setattr(subject.parent, "checkpoint_reference", lambda path: dict(path=path))
    monkeypatch.setattr(subject, "entry", lambda path: dict(path=str(path)))
    records = []
    monkeypatch.setattr(subject, "publish", lambda path, value: records.append(value))
    with pytest.raises(ValueError, match="really exited zero"):
        f.controller.accept_finished(runner)
    assert not f.controller.pilot_accepted and not accepted
    exited["returncode"] = 0
    f.controller.accept_finished(runner)
    assert f.controller.pilot_accepted and accepted == [runner]
    assert (f.controller.accepted_new_updates, f.controller.accepted_new_outers) == (1668, 5)
    assert records[-1]["restored_completed_responses"] == 261
    assert records[-1]["actual_new_response_calls"] == 186


def test_actual_worker_training_result_crosses_controller_pilot_validator(tmp_path, monkeypatch):
    # Reuse the actual worker orchestration fixture: the unchanged real trainer
    # creates the result through the V40 worker. Do not independently invent
    # boundary field names on both sides of this integration contract.
    fixture = importlib.import_module("test_finance_v40_worker").episode
    episode = fixture.__wrapped__(tmp_path, monkeypatch)
    episode.run("distribution")
    episode.cuda.initialized = False
    result = episode.run("train")
    runner = subject.ContextRunner.__new__(subject.ContextRunner)
    runner.context, runner.protocol = episode.context, episode.plan
    runner.active = {"train": dict(launch=dict(gpu_index=4, gpu_uuid="GPU-fixed"))}
    runner.evaluation, runner.recovery_pilot = False, True
    actual_commit_checks = []
    monkeypatch.setattr(
        subject.parent,
        "validate_training_commit",
        lambda context, actual: actual_commit_checks.append((context, actual)),
    )
    runner.lifecycle_result_validator("train", result)
    assert actual_commit_checks == [(episode.context, result)]
    assert result["registered_training_stop_step"] == 299
    assert result["execution_boundary_policy_protocol_id"] == episode.plan["id"]
    with pytest.raises(ValueError, match="SFT299"):
        runner.lifecycle_result_validator(
            "train", dict(result, execution_boundary_policy_protocol_id="another-protocol")
        )


@pytest.fixture
def cold_run(monkeypatch, tmp_path):
    controller = subject.Controller.__new__(subject.Controller)
    controller.root = tmp_path / "recovery_02"
    controller.protocol = dict(id="new")
    controller.inherited = dict(inherited_resource_wait_seconds=28088)
    controller._original_inherited_wait = 28088
    controller._registered_at = 1000
    controller._stop_audit = lambda: None
    calls, records = [], []
    monkeypatch.setattr(
        subject, "__file__", str(controller.root / "implementation/finqa_v40_controller.py")
    )
    monkeypatch.setattr(subject.time, "time", lambda: 1025.5)
    monkeypatch.setattr(subject, "publish", lambda path, value: records.append((path, value)))
    monkeypatch.setattr(subject, "own_command", lambda: ["frozen-v40", "run"])
    monkeypatch.setattr(subject, "birth", lambda pid: "birth")
    monkeypatch.setattr(
        subject.stop_signals, "audit_signal_installations", lambda **kw: nullcontext()
    )
    monkeypatch.setattr(
        subject.parent.Controller, "run", lambda self: calls.append(self.resource_wait_used) or True
    )
    return SimpleNamespace(controller=controller, calls=calls, records=records)


def test_run_charges_registration_and_cpu_initialization_wall_before_dispatch(cold_run):
    f = cold_run
    assert f.controller.run() is True
    assert f.calls == [28114]
    assert f.records[0][1]["initialization_wall_seconds"] == 25.5
    assert f.records[0][1]["inherited_global_wait_at_dispatch"] == 28114
    assert f.records[0][1]["independent_recovery_not_clean_handoff"] is True


def test_initialization_budget_exhaustion_never_calls_runtime(cold_run):
    f = cold_run
    f.controller._original_inherited_wait = 86400 - 25
    with pytest.raises(subject.DurablePause, match="24-hour"):
        f.controller.run()
    assert not f.calls and not f.records


@pytest.mark.parametrize(
    "signal_received,cooperative,expected",
    [
        (True, True, "COOPERATIVE_RESPONSE_BOUNDARY_PAUSE"),
        (True, False, "OBSERVED_STOP_SIGNAL"),
        (False, False, "UNCLASSIFIED_STAGE_OR_CONTROLLER_FAILURE"),
    ],
)
def test_worker_embedded_stop_receipts_are_classified_without_guessing_sender(
    tmp_path, signal_received, cooperative, expected
):
    controller = subject.Controller.__new__(subject.Controller)
    controller.root, controller.protocol = tmp_path, dict(id="new")
    subject.publish(
        tmp_path / "failure/record.json",
        dict(error_type="ValueError", error="worker reported failure"),
    )
    worker = tmp_path / "contexts/seed389/full/step0298_outer/replay_R3/failure/record.json"
    subject.publish(
        worker,
        dict(
            stop_evidence=dict(
                received_signals=[dict(signal_number=15)] if signal_received else []
            ),
            failure_classification="COOPERATIVE_RESPONSE_BOUNDARY_PAUSE"
            if cooperative
            else "STAGE_FAILURE_NO_RETRY",
            durable_replay_checkpoint=dict(id="saved") if cooperative else None,
        ),
    )
    # Mere existence of an empty audit record must not imply a signal.
    subject.publish(tmp_path / "signal_audit/record.json", dict(received_signals=[]))
    controller._stop_audit()
    result = subject.checked(tmp_path / "stop_audit/record.json")
    assert result["stop_classification"] == expected
    assert result["received_stop_signal_observed"] is signal_received
    assert result["signal_sender_attribution"] == ("unknown" if signal_received else "not_observed")
    assert result["numerical_failure_inferred_from_signal"] is False
    assert result["failed_stage_automatically_retried"] is False


def test_complete_training_only_enqueues_missing_endpoint_answers(monkeypatch):
    controller = subject.Controller.__new__(subject.Controller)
    coordinates = {(seed, arm) for seed in subject.parent.SEEDS for arm in subject.parent.ARMS}
    controller.pilot_accepted = controller._remaining_frontier_installed = True
    controller.completed_arms = coordinates
    controller.completed_evaluations = coordinates - {(389, "Full")}
    controller.active_coordinate, controller.runs = {}, []
    controller.create_context = lambda *a, **kw: pytest.fail("completed training cannot repeat")
    generated = []

    def create(coordinate):
        generated.append(coordinate)
        controller.runs.append(SimpleNamespace(evaluation=True, context=dict(seed=389, arm="Full")))

    controller.create_evaluation = create
    controller.enqueue_remaining()
    controller.enqueue_remaining()
    assert generated == [(389, "Full")]


@pytest.fixture
def partial_class(frontier, monkeypatch):
    f = frontier
    context = f.values["other"]
    context.update(seed=251, arm="C-only", step=1192)
    item = f.items[1]
    item["partial_class_recovery"] = dict(subject.CLASS_COMPLETION)
    for stage in item["stage_bindings"]:
        if stage != "shard02":
            item["stage_bindings"][stage] = dict(protocol_scope="current")
    item["phase_deadlines_epoch"] = dict(class_gradients=900)
    f.controller.protocol.update(
        partial_class_completion=dict(subject.CLASS_COMPLETION),
        partial_class_completion_authorization=dict(
            path="explicit-class-authority", id="authority"
        ),
        cpu_affinity=subject.admission.CPU_AFFINITY,
    )
    f.controller.disk_gate = lambda projection: None
    f.controller.pilot_accepted = True
    runner = f.controller._install_context(item)
    runner._lifecycle_launch_gate = lambda: None
    clock = SimpleNamespace(now=1000.0)
    monkeypatch.setattr(subject.time, "time", lambda: clock.now)
    monkeypatch.setattr(subject.time, "monotonic", lambda: clock.now)
    launched = []

    def popen(command, **kwargs):
        launched.append(command)
        return SimpleNamespace(pid=10000 + len(launched))

    monkeypatch.setattr(subject.subprocess, "Popen", popen)
    monkeypatch.setattr(subject, "birth", lambda pid: "mock-birth")
    monkeypatch.setattr(subject.parent, "worker_environment", lambda row: {})
    return SimpleNamespace(runner=runner, clock=clock, launched=launched, controller=f.controller)


def test_partial_class_only_keeps_successful_shard02_and_does_not_start_window_on_inspect(
    partial_class,
):
    f = partial_class
    assert f.runner.pending() == ["shard00", "shard01", "shard03"]
    assert f.runner.dispatched == {"shard02"}
    assert f.runner.compute_used == 44470
    assert f.runner.stage_limit("shard00") == ("class_gradients", 14400)
    assert not (f.runner.root / "class_recovery_window/record.json").exists()
    with pytest.raises(ValueError, match="three explicitly authorized"):
        f.runner.stage_limit("shard02")


def test_three_remaining_shards_share_one_absolute_four_hour_window(partial_class):
    f = partial_class
    deadlines = []
    for when, stage, gpu in ((1000, "shard00", 3), (1600, "shard01", 4), (2200, "shard03", 5)):
        f.clock.now = when
        row = dict(index=gpu, uuid=subject.admission.GPU_UUIDS[str(gpu)])
        f.runner.launch(stage, row, object())
        deadlines.append(f.runner.active[stage]["launch"]["deadline_epoch"])
    assert deadlines == [15400, 15400, 15400]
    window = subject.checked(f.runner.root / "class_recovery_window/record.json")
    assert window["started_epoch"] == 1000 and window["first_dispatched_shard"] == "shard00"
    assert window["original_class_deadline_epoch"] == 900
    assert window["allowed_stages"] == ["shard00", "shard01", "shard03"]
    assert f.runner.compute_used == 44470  # New phase window does not clear old compute.
    assert f.controller.resource_wait_used == 28088


def test_class_completion_window_does_not_extend_original_outer_remainder(partial_class):
    f = partial_class
    f.runner.compute_used = subject.parent.OUTER_COMPUTE_SECONDS - 1000
    f.runner.launch("shard00", dict(index=3, uuid=subject.admission.GPU_UUIDS["3"]), object())
    assert f.runner.active["shard00"]["launch"]["deadline_epoch"] == 2000
    window = subject.checked(f.runner.root / "class_recovery_window/record.json")
    assert window["deadline_epoch"] == 15400


def test_partial_class_window_expires_without_affecting_later_phase_budget(partial_class):
    f = partial_class
    f.runner.class_completion_window("shard00", create=True)
    f.clock.now = 15400
    with pytest.raises(subject.DurablePause, match="shared four-hour"):
        f.runner.stage_limit("shard01")
    assert f.runner.stage_limit("virtual_point") == ("virtual_existing", 7200)


def test_explicit_class_exception_cannot_move_to_another_coordinate(partial_class):
    f = partial_class
    f.runner.context = dict(f.runner.context, seed=389)
    with pytest.raises(ValueError, match="three explicitly authorized"):
        f.runner.class_completion_window("shard00", create=True)
    assert not (f.runner.root / "class_recovery_window/record.json").exists()


def test_ungranted_partial_class_keeps_old_expired_deadline(partial_class):
    f = partial_class
    del f.runner.inherited["partial_class_recovery"]
    with pytest.raises(subject.DurablePause, match="inherited phase deadline"):
        f.runner.stage_limit("shard00")


def test_new_device_scope_uses_expected_priority_and_numas_without_mutating_history():
    historical = importlib.import_module("finqa_v39_admission")
    assert historical.ALLOWED_GPUS == (3, 4, 5, 6, 7)
    assert subject.admission.original is not historical
    assert subject.DISPATCH_ORDER == (3, 4, 5, 7, 0, 1, 2, 6)
    assert all(subject.admission.CPU_AFFINITY[str(gpu)] == "0-37,76-113" for gpu in (0, 1, 2, 3))
    assert all(subject.admission.CPU_AFFINITY[str(gpu)] == "38-75,114-151" for gpu in (4, 5, 6, 7))


def test_pool_prefers_original_cards_and_honors_live_uuid_locks(monkeypatch, tmp_path):
    plan = dict(id="new", output_root=str(tmp_path), gpu_uuids=subject.admission.GPU_UUIDS)
    controller = SimpleNamespace(protocol=plan, disk_gate=lambda projection: None)
    pool = subject.parent.LeasePool(controller)
    runner = SimpleNamespace(active={}, disk_projection=lambda stage: 0)
    rows = [
        dict(index=gpu, uuid=subject.admission.GPU_UUIDS[str(gpu)], processes=[], free_mib=80000)
        for gpu in range(8)
    ]
    monkeypatch.setattr(subject.parent, "inventory", lambda: rows)
    monkeypatch.setattr(subject.parent, "host_memory", lambda: dict(available_bytes=1024**4))
    monkeypatch.setattr(subject.parent, "TRAINING_ROOT", tmp_path / "training")
    selected = []
    leases = []
    for _ in range(4):
        row, lease = pool.try_acquire(runner, "train")
        selected.append(row["index"])
        leases.append(lease)
    assert selected == [3, 4, 5, 7]
    assert pool.try_acquire(runner, "train") is None
    for lease in leases:
        lease.close()


@pytest.mark.parametrize("gpu", [0, 1, 2, 6])
def test_expanded_device_is_used_only_with_its_actual_free_uuid_lease(monkeypatch, tmp_path, gpu):
    plan = dict(id="new", output_root=str(tmp_path), gpu_uuids=subject.admission.GPU_UUIDS)
    controller = SimpleNamespace(protocol=plan, disk_gate=lambda projection: None)
    pool = subject.parent.LeasePool(controller)
    runner = SimpleNamespace(active={}, disk_projection=lambda stage: 0)
    row = dict(index=gpu, uuid=subject.admission.GPU_UUIDS[str(gpu)], processes=[], free_mib=80000)
    monkeypatch.setattr(subject.parent, "inventory", lambda: [row])
    monkeypatch.setattr(subject.parent, "host_memory", lambda: dict(available_bytes=1024**4))
    monkeypatch.setattr(subject.parent, "TRAINING_ROOT", tmp_path / "training")
    path = tmp_path / "training/locks" / ("gpu-" + subject.parent.digest(row["uuid"]) + ".lock")
    path.parent.mkdir(parents=True)
    with path.open("a") as other_owner:
        fcntl.flock(other_owner, fcntl.LOCK_EX | fcntl.LOCK_NB)
        assert pool.try_acquire(runner, "train") is None
        assert not pool.leases
    selected, lease = pool.try_acquire(runner, "train")
    assert selected["index"] == lease.gpu == gpu
    lease.close()
