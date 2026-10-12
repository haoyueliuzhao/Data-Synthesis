"""CPU-only V39 scope isolation, restored frontier and migration orchestration."""

import importlib
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest

sys.path.insert(0, str(Path(__file__).parents[1] / "scripts"))
subject = importlib.import_module("finqa_v39_controller")


@pytest.fixture
def plan(tmp_path):
    return dict(
        id="new-plan",
        output_root=str(tmp_path),
        gpu_uuids=dict(subject.admission.GPU_UUIDS),
        allowed_gpu_indices=list(subject.ALLOWED_GPUS),
    )


def row(gpu):
    return dict(
        index=gpu, uuid=subject.admission.GPU_UUIDS[str(gpu)], processes=[], free_mib=80 * 1024
    )


def test_historical_validator_and_new_runtime_have_distinct_module_scopes():
    assert subject.parent is not subject.verifier.parent
    assert subject.parent.ALLOWED_GPUS == (3, 4, 5, 6, 7)
    assert subject.verifier.parent.ALLOWED_GPUS == (3, 4, 5, 7)
    assert subject.parent.LeasePool.try_acquire.__globals__ is subject.parent.__dict__
    assert (
        subject.verifier.parent.LeasePool.try_acquire.__globals__
        is subject.verifier.parent.__dict__
    )
    assert subject._base_check_result.__globals__ is subject.parent.__dict__
    assert subject.parent.ContextRunner is subject.ContextRunner
    assert subject.parent.checked_protocol is subject.checked_protocol
    assert subject.verifier.parent.checked_protocol is not subject.checked_protocol


def test_gpu6_is_newly_eligible_but_not_in_historical_four_card_gate(plan):
    assert subject.eligible(row(6), plan)
    assert not subject.verifier.parent.eligible(row(6), plan)
    for bad in (
        dict(row(6), uuid="changed"),
        dict(row(6), processes=[dict(pid=1)]),
        dict(row(6), free_mib=73727),
        dict(row(6), index=0),
    ):
        assert not subject.eligible(bad, plan)


def test_historical_result_cannot_acquire_new_gpu6_authority(plan):
    old = dict(plan, allowed_gpu_indices=[3, 4, 5, 7])
    with pytest.raises(ValueError, match="actual protocol owner"):
        subject.check_result(old, "train", dict(gpu_index=6))


def test_gpu6_withdrawal_affects_new_admission_only(plan, tmp_path):
    active = SimpleNamespace(gpu=6, active=True)
    assert subject.eligible(row(6), plan)
    subject.publish(
        tmp_path / "queue/gpu6_withdrawal/record.json",
        dict(
            protocol_id=plan["id"],
            gpu_index=6,
            stop_future_dispatch=True,
        ),
    )
    assert not subject.eligible(row(6), plan)
    assert all(subject.eligible(row(gpu), plan) for gpu in (3, 4, 5, 7))
    assert active.active is True  # The admission check has no running-worker mutation.


def test_invalid_withdrawal_is_fail_closed(plan, tmp_path):
    subject.publish(
        tmp_path / "queue/gpu6_withdrawal/record.json",
        dict(
            protocol_id="foreign",
            gpu_index=6,
            stop_future_dispatch=True,
        ),
    )
    with pytest.raises(ValueError, match="invalid temporary GPU withdrawal"):
        subject.eligible(row(6), plan)


def test_lease_pool_stays_capped_at_four_including_cpu_or_draining(monkeypatch, plan):
    controller = SimpleNamespace(protocol=plan)
    pool = subject.parent.LeasePool(controller)
    pool.leases = {gpu: object() for gpu in (3, 4, 5, 6)}
    monkeypatch.setattr(
        subject.parent, "inventory", lambda: pytest.fail("must not inspect fifth card")
    )
    assert pool.try_acquire(object(), "train") is None
    assert len(pool.leases) == 4


def test_real_file_lease_pool_can_select_gpu6_without_changing_old_validator(
    monkeypatch, plan, tmp_path
):
    controller = SimpleNamespace(protocol=plan, disk_gate=lambda _: None)
    pool = subject.parent.LeasePool(controller)
    runner = SimpleNamespace(active={}, disk_projection=lambda stage: 0)
    monkeypatch.setattr(subject.parent, "TRAINING_ROOT", tmp_path / "training")
    monkeypatch.setattr(subject.parent, "inventory", lambda: [row(6)])
    monkeypatch.setattr(subject.parent, "host_memory", lambda: dict(available_bytes=400 * 1024**3))
    result, lease = pool.try_acquire(runner, "train")
    assert result["index"] == lease.gpu == 6
    assert list(pool.leases) == [6]
    assert subject.verifier.parent.ALLOWED_GPUS == (3, 4, 5, 7)
    lease.close()
    assert not pool.leases


@pytest.fixture
def frontier(monkeypatch, tmp_path, plan):
    origin = tmp_path / "old/context"
    target = tmp_path / "new/context"
    context = dict(
        id="same-point",
        seed=251,
        arm="C-only",
        due_outer=True,
        task_plan="tasks",
        feedback=dict(mode="sealed_existing"),
    )
    values = {
        "context": context,
        "tasks": {},
        "old-protocol": dict(id="old-plan", allowed_gpu_indices=[3, 4, 5, 7]),
    }
    bindings = {}
    for stage in (*subject.parent.SHARDS, "virtual_point", "replay_R3"):
        values[stage + "-result"] = dict(stage=stage, protocol_id="old-plan")
        values[stage + "-exit"] = dict(returncode=0)
        bindings[stage] = dict(
            protocol_scope="parent", result=stage + "-result", exit=stage + "-exit"
        )
    bindings["distribution"] = bindings["train"] = dict(protocol_scope="current")
    inherited = dict(
        new_context_directory=str(target),
        original_context="context",
        origin_context_directory=str(origin),
        parent_protocol="old-protocol",
        stage_bindings=bindings,
        inherited_compute_seconds=12345,
        phase_deadlines_epoch={"class_gradients": 900, "replay_R3": 950},
    )
    controller = subject.Controller.__new__(subject.Controller)
    controller.protocol = plan
    controller.runs = []
    controller.active_coordinate = {}
    controller._frontier_installed = False
    controller.inherited = dict(context_inheritances=[inherited])
    controller.resource_wait_used = 123
    controller.has_draining = lambda: False
    checks = []
    monkeypatch.setattr(subject, "read_ref", lambda ref: values[ref])
    monkeypatch.setattr(subject.parent, "read_ref", lambda ref: values[ref])
    monkeypatch.setattr(
        subject.inheritance, "resolve_origin_context", lambda directory, protocol: origin
    )
    monkeypatch.setattr(
        subject,
        "check_result",
        lambda protocol, stage, result, tasks: checks.append(
            (protocol["id"], stage, result["protocol_id"])
        ),
    )
    monkeypatch.setattr(subject.ContextRunner, "update", lambda *args, **kwargs: None)
    monkeypatch.setattr(subject.Controller, "enqueue_remaining", lambda self: None)
    return SimpleNamespace(
        controller=controller, inherited=inherited, context=context, values=values, checks=checks
    )


def test_completed_parent_stages_prefilled_in_original_scope_and_not_redispatched(frontier):
    f = frontier
    f.controller.create_context(subject.parent.FIRST, pilot=True)
    runner = f.controller.runs[0]
    assert runner.pending() == ["distribution"]
    assert runner.compute_used == 12345
    assert runner.dispatched == set(subject.parent.SHARDS) | {"virtual_point", "replay_R3"}
    assert all(old == actual == "old-plan" for old, _, actual in f.checks)
    assert f.controller.active_coordinate[(251, "C-only")] is runner
    runner._lifecycle_launch_gate = lambda: None
    with pytest.raises(ValueError, match="unregistered next stage"):
        runner.launch("replay_R3", row(6), object())
    with pytest.raises(ValueError, match="one restoration"):
        f.controller.create_context(subject.parent.FIRST, pilot=True)


def test_nonzero_parent_exit_rejects_frontier(frontier):
    f = frontier
    f.values["replay_R3-exit"] = dict(returncode=1)
    with pytest.raises(ValueError, match="actually exited zero"):
        f.controller.create_context(subject.parent.FIRST, pilot=True)


def test_distinct_phase_budgets_inherit_without_resetting_completed_phase(frontier, monkeypatch):
    f = frontier
    f.controller.create_context(subject.parent.FIRST, pilot=True)
    runner = f.controller.runs[0]
    monkeypatch.setattr(subject.time, "time", lambda: 1000)
    assert runner.stage_limit("distribution") == ("distribution", 7200)
    assert runner.stage_limit("train") == ("train", 28800)
    runner.inherited["phase_deadlines_epoch"]["distribution"] = 1100
    assert runner.stage_limit("distribution") == ("distribution", 100)
    with pytest.raises(subject.DurablePause, match="inherited phase deadline"):
        runner.stage_limit("replay_R3")
    assert runner.compute_used == 12345


def test_all_complete_training_still_enqueues_missing_endpoint_generation(monkeypatch, plan):
    controller = subject.Controller.__new__(subject.Controller)
    coordinates = {(seed, arm) for seed in subject.parent.SEEDS for arm in subject.parent.ARMS}
    controller.pilot_accepted = True
    controller.completed_arms = coordinates
    controller.completed_evaluations = coordinates - {(137, "Full"), (389, "Static")}
    controller.active_coordinate = {}
    controller.runs = []
    created = []
    controller.create_context = lambda *args, **kwargs: pytest.fail(
        "completed training must not repeat"
    )

    def generate(coordinate):
        created.append(coordinate)
        controller.runs.append(
            SimpleNamespace(
                evaluation=True, context=dict(zip(("seed", "arm"), coordinate, strict=True))
            )
        )

    controller.create_evaluation = generate
    controller.enqueue_remaining()
    controller.enqueue_remaining()
    assert set(created) == {(137, "Full"), (389, "Static")} and len(created) == 2


@pytest.fixture
def migration(monkeypatch, tmp_path):
    root = tmp_path / "new"
    monkeypatch.setattr(subject, "ROOT", root)
    monkeypatch.setattr(subject, "__file__", str(root / "implementation/finqa_v39_controller.py"))
    monkeypatch.setattr(subject, "checked_implementation", lambda root: {})
    monkeypatch.setattr(subject, "checked", lambda path: dict(user_consent="同意"))
    monkeypatch.setattr(subject, "entry", lambda path: dict(path=str(path)))
    monkeypatch.setattr(subject, "birth", lambda pid: "birth")
    monkeypatch.setattr(
        subject.handoff,
        "process_identity",
        lambda pid: dict(birth="birth", argv=["python", "-u", "-B", "frozen.py", "migrate"]),
    )
    records, order, runs = [], [], []
    monkeypatch.setattr(
        subject, "publish", lambda path, record: records.append((path, record)) or record
    )
    monkeypatch.setattr(subject, "initialize", lambda *args, **kwargs: order.append("initialize"))

    class Controller:
        def __init__(self, _root):
            order.append("construct")
            self.inherited = dict(inherited_resource_wait_seconds=500)
            self.resource_wait_used = 500
            self.protocol = dict(id="new")

        def resource_wait_gate(self):
            order.append("gate")
            if self.resource_wait_used >= 86400:
                raise subject.DurablePause("resource wait budget exhausted")

        def run(self):
            order.append("run")
            runs.append(self.resource_wait_used)
            return True

    monkeypatch.setattr(subject, "Controller", Controller)
    state = SimpleNamespace(billing=550.25, records=records, order=order, runs=runs, root=root)

    def handoff_run(_root, *, on_quiesced, validate_quiescent):
        assert validate_quiescent is subject.preflight_quiescent
        order.append("handoff")

        def release():
            assert order[-1] == "construct"
            order.append("release")
            return dict(global_resource_wait_seconds=state.billing)

        return on_quiesced(dict(status="COMPLETE"), release)

    monkeypatch.setattr(subject.handoff, "run", handoff_run)
    return state


def test_same_process_migration_builds_cpu_state_before_release_and_charges_initialization(
    migration,
):
    m = migration
    assert subject.migrate(m.root) is True
    assert m.order == ["handoff", "initialize", "construct", "release", "gate", "run"]
    assert m.runs == [551]
    launches = [value for path, value in m.records if path.parent.name == "launch_01"]
    assert launches[0]["inherited_global_wait_at_dispatch"] == 551


def test_initialization_crossing_budget_never_starts_controller(migration):
    m = migration
    m.billing = 86399.9  # Conservative ceil consumes the last fraction, never resets it.
    with pytest.raises(subject.DurablePause, match="resource wait budget exhausted"):
        subject.migrate(m.root)
    assert not m.runs
    assert not any(path.parent.name == "launch_01" for path, _ in m.records)


def test_own_command_keeps_interpreter_flags(monkeypatch):
    command = ["/env/python", "-u", "-B", "/frozen/controller.py", "migrate"]
    monkeypatch.setattr(subject, "birth", lambda pid: "expected")
    monkeypatch.setattr(
        subject.handoff, "process_identity", lambda pid: dict(birth="expected", argv=command)
    )
    assert subject.own_command() == command


def test_own_command_rejects_changed_birth(monkeypatch):
    monkeypatch.setattr(subject, "birth", lambda pid: "expected")
    monkeypatch.setattr(
        subject.handoff, "process_identity", lambda pid: dict(birth="other", argv=["python"])
    )
    with pytest.raises(ValueError, match="identity unavailable"):
        subject.own_command()
