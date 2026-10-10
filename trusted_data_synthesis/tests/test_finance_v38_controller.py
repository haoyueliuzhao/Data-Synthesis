"""CPU tests for recovery routing, inherited budgets and admission wait accounting."""

import copy
import importlib
import json
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest

sys.path.insert(0, str(Path(__file__).parents[1] / "scripts"))
queue = importlib.import_module("finqa_v38_controller")


class Clock:
    current = 1000.0

    def monotonic(self):
        return self.current

    def time(self):
        return 1_800_000_000 + self.current


class Process:
    def __init__(self, pid=41, code=None):
        self.pid, self.code = pid, code

    def poll(self):
        return self.code


class Lease:
    closed = False

    def close(self):
        self.closed = True


@pytest.fixture
def manager(tmp_path, monkeypatch):
    value = queue.Controller.__new__(queue.Controller)
    value.root = tmp_path / "recovery_01"
    value.protocol = queue.publish(
        value.root / "protocol/record.json",
        dict(
            gpu_uuids={str(i): f"GPU-{i}" for i in queue.ALLOWED_GPUS},
            cpu_affinity={str(i): "0-3" for i in queue.ALLOWED_GPUS},
        ),
    )
    value.inherited = dict(
        original_context_id="parent-context",
        inherited_compute_seconds=9000,
        inherited_distribution_seconds=51,
        inherited_resource_wait_seconds=120,
    )
    value.resource_wait_used = 120.0
    value._resource_waiting, value._resource_accounting_at = False, 1000.0
    value._idle_wait_intervals, value._worker_wait_intervals = [], {}
    value._pre_cuda_waiters, value._last_wait_sequences, value._admission_stop_errors = {}, {}, []
    value.runs, value.active_coordinate, value.latest = [], {}, {}
    value.stop = value.pilot_accepted = False
    value.draining_episode, value.draining_episode_count = None, 0
    value.completed_arms = {(137, "Static"), (251, "Static")}
    value.completed_evaluations = set(value.completed_arms)
    value.accepted_new_updates = value.accepted_new_outers = 0
    value.disk_gate, value.source_bindings = lambda _: None, {}
    value.training = value.rt = value.original_cache = object()
    clock = Clock()
    monkeypatch.setattr(queue, "time", clock)
    monkeypatch.setattr(queue.parent, "time", clock)
    monkeypatch.setattr(queue.parent._v36.lifecycle, "time", clock)
    return value, clock


def make_context(manager, name="parent-context", *, due=True):
    path = manager.root / f"metadata/{name}/task_plan.json"
    queue.publish(path, dict(assignments=[], tasks=[]))
    return dict(
        id=name,
        seed=137,
        arm="C-only",
        step=1192,
        due_outer=due,
        task_plan=queue.entry(path) if due else None,
        feedback=dict(mode="sealed_existing", expected_point_id="actual-point"),
        checkpoint={"path": "original-step1192"},
        parameter_spec=[],
    )


def make_runner(manager, name="parent-context", *, due=True):
    result = queue.ContextRunner(manager, manager.root / name, make_context(manager, name, due=due))
    manager.runs.append(result)
    return result


def active(runner, *, pid=41, code=None):
    item = dict(
        launch=dict(
            stage="distribution",
            pid=pid,
            birth=f"birth-{pid}",
            gpu_index=4,
            gpu_uuid="GPU-4",
            deadline_epoch=1_800_010_000,
        ),
        process=Process(pid, code),
        lock=Lease(),
        started_monotonic=900.0,
        stage_deadline_monotonic=2000,
    )
    runner.active["distribution"] = item
    return item


def heartbeat(manager, runner, item, **changes):
    body = dict(
        schema="v38_pre_cuda_admission.v1",
        protocol_id=manager.protocol["id"],
        context_id=runner.context["id"],
        **item["launch"],
        cuda_initialized=False,
        phase="WAITING",
        sequence=0,
        observed_monotonic=995.0,
        waiting_started_monotonic=990.0,
        waiting_finished_monotonic=None,
        waiting_seconds=5.0,
    )
    body.update(changes)
    path = runner.root / "distribution/pre_cuda_wait/status.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(dict(body, id=queue.digest(body))) + "\n")


def test_interval_union_counts_overlapping_touching_and_duplicate_waits_once():
    values = [(8, 9), (1, 2), (2, 5), (3, 4), (1, 2), (7, 7)]
    original = copy.deepcopy(values)
    assert queue.merged_intervals(values) == [(1, 5), (7, 7), (8, 9)]
    assert values == original and queue.merged_intervals([]) == []


@pytest.mark.parametrize(
    "interval", [(-1, 2), (3, 2), (True, 2), (1, float("nan")), (1, float("inf"))]
)
def test_interval_union_rejects_invalid_clocks(interval):
    with pytest.raises(ValueError, match="invalid external-resource"):
        queue.merged_intervals([interval])


@pytest.mark.parametrize(
    "field,value",
    [
        ("protocol_id", "parent"),
        ("context_id", "other"),
        ("stage", "train"),
        ("pid", 42),
        ("birth", "other-birth"),
        ("gpu_index", 7),
        ("gpu_uuid", "other-GPU"),
        ("deadline_epoch", 1_800_010_001),
        ("cuda_initialized", True),
    ],
)
def test_wait_heartbeat_requires_exact_owned_dispatch(manager, field, value):
    control, _ = manager
    runner = make_runner(control)
    item = active(runner)
    heartbeat(control, runner, item, **{field: value})
    with pytest.raises(ValueError, match="does not belong"):
        control.capture_wait(runner, "distribution", item)
    assert not control._worker_wait_intervals


def test_waiting_heartbeat_freshness_and_sequence_are_enforced(manager):
    control, clock = manager
    runner = make_runner(control)
    item = active(runner)
    heartbeat(control, runner, item)
    control.capture_wait(runner, "distribution", item)
    clock.current = 1060
    with pytest.raises(ValueError, match="heartbeat stale"):
        control.capture_wait(runner, "distribution", item)
    clock.current = 1000
    heartbeat(control, runner, item, sequence=2, observed_monotonic=999, waiting_seconds=9)
    control.capture_wait(runner, "distribution", item)
    heartbeat(control, runner, item, sequence=1, observed_monotonic=999, waiting_seconds=9)
    with pytest.raises(ValueError, match="sequence reversed"):
        control.capture_wait(runner, "distribution", item)


def test_short_ready_between_polls_remains_counted_after_real_exit(manager):
    control, _ = manager
    runner = make_runner(control)
    item = active(runner, code=0)
    heartbeat(
        control,
        runner,
        item,
        phase="READY",
        sequence=1,
        waiting_started_monotonic=992,
        waiting_finished_monotonic=995,
        waiting_seconds=3,
    )
    runner.record_exit("distribution")
    assert item["lock"].closed and not runner.active and not control._pre_cuda_waiters
    assert control.resource_wait_used == 123
    control.account_resource_wait()
    assert control.resource_wait_used == 123


def test_final_exit_wait_budget_is_checked_after_releasing_real_exited_lease(manager):
    control, _ = manager
    control.inherited["inherited_resource_wait_seconds"] = queue.RESOURCE_WAIT_SECONDS - 2
    runner = make_runner(control)
    item = active(runner, code=0)
    heartbeat(control, runner, item, phase="READY", waiting_finished_monotonic=995)
    with pytest.raises(queue.DurablePause, match="resource wait budget exhausted"):
        runner.record_exit("distribution")
    assert not runner.active and item["lock"].closed
    assert control.resource_wait_used == queue.RESOURCE_WAIT_SECONDS + 3


@pytest.mark.parametrize("stopped", [False, True])
def test_invalid_heartbeat_does_not_block_actual_exit_release_during_shutdown(manager, stopped):
    control, _ = manager
    runner = make_runner(control)
    item = active(runner, code=0)
    heartbeat(control, runner, item, protocol_id="wrong")
    if stopped:
        assert runner.record_exit("distribution", stopped=True) == 0
        assert len(control._admission_stop_errors) == 1
    else:
        with pytest.raises(ValueError, match="does not belong"):
            runner.record_exit("distribution")
    assert not runner.active and item["lock"].closed
    exited = queue.checked(runner.root / "distribution/exit/record.json")
    assert exited["returncode"] == 0 and exited["stop_requested"] is stopped


def test_worker_waits_and_idle_waits_are_charged_as_one_global_union(manager):
    control, clock = manager
    first, second = make_runner(control, "a"), make_runner(control, "b")
    a, b = active(first, pid=41), active(second, pid=42)
    heartbeat(control, first, a, waiting_started_monotonic=990, observed_monotonic=999)
    heartbeat(control, second, b, waiting_started_monotonic=994, observed_monotonic=998)
    control._idle_wait_intervals = [(980, 993)]
    control.account_resource_wait()
    assert control.resource_wait_used == 139 and len(control._pre_cuda_waiters) == 2
    clock.current = 1005
    heartbeat(control, first, a, sequence=1, observed_monotonic=1004, waiting_seconds=14)
    heartbeat(
        control,
        second,
        b,
        sequence=1,
        observed_monotonic=1003,
        waiting_started_monotonic=994,
        waiting_seconds=9,
    )
    control.account_resource_wait()
    assert control.resource_wait_used == 144


def test_normal_owned_queueing_is_not_external_wait(manager):
    control, clock = manager
    runner = make_runner(control)
    active(runner)
    clock.current += 10
    control.account_resource_wait()
    assert control.resource_wait_used == 120
    runner.active.clear()
    control._resource_waiting = True
    clock.current += 8
    control.account_resource_wait()
    assert control.resource_wait_used == 128


def test_parent_six_results_are_inherited_without_relabelling_and_only_distribution_pending(
    manager, monkeypatch
):
    control, _ = manager
    origin = control.root.parent / "parent_context"
    old_context = make_context(control)
    old_context.pop("id")
    old_context = queue.publish(origin / "context/record.json", old_context)
    old_protocol = queue.publish(origin / "protocol/record.json", dict(parent=True))
    bindings, old_results = {}, {}
    for stage in queue.inheritance.INHERITED_STAGES:
        result_path, exit_path = origin / stage / "result.json", origin / stage / "exit.json"
        old_results[stage] = queue.publish(
            result_path,
            dict(
                protocol_id=old_protocol["id"],
                context_id=old_context["id"],
                stage=stage,
                status="COMPLETE",
            ),
        )
        queue.publish(exit_path, dict(returncode=0))
        bindings[stage] = dict(result=queue.entry(result_path), exit=queue.entry(exit_path))
    control.inherited.update(
        original_context=queue.entry(origin / "context/record.json"),
        original_context_id=old_context["id"],
        parent_protocol=queue.entry(origin / "protocol/record.json"),
        origin_context_directory=str(origin),
        new_context_directory=str(control.root / "alias"),
        stage_bindings=bindings,
    )
    monkeypatch.setattr(queue.inheritance, "resolve_origin_context", lambda *_args: origin)
    verified = []

    def check(owner, stage, result, _task_plan):
        assert owner["id"] == old_protocol["id"] == result["protocol_id"]
        verified.append(stage)

    monkeypatch.setattr(queue.parent, "check_result", check)
    runner = control.create_context(queue.FIRST, pilot=True)
    assert runner.pending() == ["distribution"]
    assert runner.dispatched == set(queue.inheritance.INHERITED_STAGES)
    assert runner.results == old_results and verified == list(queue.inheritance.INHERITED_STAGES)
    assert runner.compute_used == 9000 and not (runner.root / "shard00/result/record.json").exists()


def test_only_original_distribution_budget_is_reduced(manager):
    control, _ = manager
    first, future = make_runner(control), make_runner(control, "future")
    assert first.stage_limit("distribution") == ("distribution", 2 * 3600 - 51)
    assert future.stage_limit("distribution") == ("distribution", 2 * 3600)
    assert first.stage_limit("train") == future.stage_limit("train") == ("train", 8 * 3600)
    assert first.stage_limit("replay_R3") == ("replay_R3", 16 * 3600)


@pytest.mark.parametrize("evaluation", [False, True])
def test_future_factories_use_recovery_runner_and_new_frozen_worker(
    manager, monkeypatch, evaluation
):
    control, clock = manager
    coordinate = (251, "Full")
    if evaluation:
        runner = control.create_evaluation(coordinate)
        stage, expected = "generate", "finqa_v38_evaluation.py"
    else:
        checkpoint = control.root / "source_checkpoint"
        checkpoint.mkdir()
        (checkpoint / "record.json").write_text(json.dumps(dict(step=600, phase="step")))
        control.latest[coordinate] = str(checkpoint)

        def prepare(directory, source, **kwargs):
            assert source == checkpoint
            assert kwargs["execution_binding"]["protocol"]["id"] == control.protocol["id"]
            assert kwargs["execution_binding"]["implementation_id"] == "new-implementation"
            return dict(id="future-600", seed=251, arm="Full", step=600, due_outer=False)

        control.context_module = SimpleNamespace(prepare_training_context=prepare)
        monkeypatch.setattr(
            queue.parent, "checked_implementation", lambda _: {"id": "new-implementation"}
        )
        runner = control.create_context(coordinate)
        stage, expected = "train", "finqa_v38_worker.py"
    assert type(runner) is queue.ContextRunner
    commands = []

    def popen(command, **kwargs):
        commands.append(command)
        return Process(123)

    monkeypatch.setattr(queue.subprocess, "Popen", popen)
    monkeypatch.setattr(queue, "birth", lambda _: "mock-birth")
    monkeypatch.setattr(queue.parent, "worker_environment", lambda _: {"CUDA_VISIBLE_DEVICES": ""})
    runner.launch(stage, dict(index=4, uuid="GPU-4"), Lease())
    command = commands[0]
    assert str(control.root / "implementation" / expected) in command
    assert command[command.index("--stage") + 1] == stage
    assert runner.active[stage]["stage_deadline_monotonic"] == clock.current + (
        12 * 3600 if evaluation else 8 * 3600
    )


def test_parent_constants_and_only_final_evaluator_module_routing_are_preserved(monkeypatch):
    assert queue.parent.ROOT == queue.PARENT_ROOT
    assert queue.parent.FILES[0] == Path(queue.parent.__file__).name == "finqa_v37_controller.py"
    assert queue.parent.ContextRunner is queue.ContextRunner
    calls = []
    monkeypatch.setattr(queue, "_parent_module", lambda path, name: calls.append((path, name)))
    new = queue.ROOT / "implementation/finqa_v37_evaluation.py"
    old = queue.PARENT_ROOT / "implementation/finqa_v37_evaluation.py"
    math = queue.ROOT / "implementation/finqa_v35_task_cache.py"
    queue._routed_module(new, "new")
    queue._routed_module(old, "old")
    queue._routed_module(math, "math")
    assert calls == [
        (new.with_name("finqa_v38_evaluation.py"), "new"),
        (old, "old"),
        (math, "math"),
    ]
