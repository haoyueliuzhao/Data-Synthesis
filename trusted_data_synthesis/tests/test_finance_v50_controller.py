"""CPU-only exclusive GPU0 continuation and Full251-first ordering tests."""

import importlib
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest

sys.path.insert(0, str(Path(__file__).parents[1] / "scripts"))
subject = importlib.import_module("finqa_v50_controller")
a = subject.admission


@pytest.fixture
def plan(tmp_path):
    return dict(
        id="v50", output_root=str(tmp_path), schema=subject.PROTOCOL_SCHEMA,
        allowed_gpu_indices=list(subject.ALLOWED_GPUS), gpu_uuids=dict(a.GPU_UUIDS),
        max_gpu_workers=1, independent_total_worker_limit=1,
        total_worker_limit_removed=False, max_workers_per_gpu=1,
        steady_gpu_indices=[0], steady_max_gpu_workers=1,
        gpu_execution_policy=a.execution_policy_record(),
        host_admission_policy=subject.host_policy_record(),
        gpu_admission_policy=subject.policy_record(),
        gpu_reservation_policy=subject.reservation_policy_record(),
        host_ram_runtime_hard_gates_unchanged=True,
    )


def context(**overrides):
    return dict(dict(seed=251, arm="Full", step=1370, due_outer=False), **overrides)


def row(gpu):
    return dict(index=gpu, uuid=a.GPU_UUIDS.get(str(gpu), "GPU-other"),
                free_mib=80 * 1024, processes=[])


@pytest.mark.parametrize("stage", a.STAGES)
def test_gpu0_accepts_each_original_stage(plan, stage):
    c = dict(context(), feedback=dict(mode="first_sampling"))
    assert a.eligible_gpu(row(0), plan, stage, c)


@pytest.mark.parametrize("gpu", [1, 2, 3, 4, 5, 6, 7])
@pytest.mark.parametrize("stage", ["train", "replay_R3", "generate"])
def test_every_other_gpu_is_rejected_even_with_free_memory(plan, gpu, stage):
    assert not a.device_scope_allows(gpu, stage, context())
    assert not a.eligible_gpu(row(gpu), plan, stage, context())


@pytest.mark.parametrize("stage", [s for s in a.STAGES if s != "train"])
def test_bootstrap_prevents_outer_work_or_endpoints_until_full251_completed(plan, stage):
    assert not a.bootstrap_stage_allows(stage, context(), full251_complete=False)
    assert a.bootstrap_stage_allows(stage, context(), full251_complete=True)


@pytest.mark.parametrize("changes", [
    dict(seed=389), dict(arm="C-only"), dict(step=1191), dict(step=1490),
    dict(step=1491), dict(step=True), dict(step=1370.0), dict(due_outer=True),
    dict(training_stop_step=1489), dict(training_stop_step=1491),
])
def test_bootstrap_cannot_restart_completed_or_different_scientific_work(plan, changes):
    assert not a.bootstrap_stage_allows("train", context(**changes), full251_complete=False)


def test_bootstrap_only_finishes_remaining_final_training_segment(plan):
    assert a.bootstrap_stage_allows("train", context(), full251_complete=False)
    assert a.bootstrap_stage_allows(
        "train", context(training_stop_step=1490), full251_complete=False
    )
    assert not a.bootstrap_stage_allows("train", None, full251_complete=False)


@pytest.mark.parametrize("state", ["INITIALIZING", "WAITING", "RUNNING", "DRAINING"])
def test_single_slot_includes_every_worker_lifecycle(plan, monkeypatch, state):
    pool = subject.LeasePool(SimpleNamespace(protocol=plan, completed_arms=set()))
    pool.leases = {gpu: SimpleNamespace(lifecycle_state=state) for gpu in (0,)}
    monkeypatch.setattr(pool, "_host_admission", lambda _: pytest.fail("cap before RAM"))
    assert pool.try_acquire(object(), "train") is None


def test_before_bootstrap_complete_other_work_waits_without_resource_query(plan, monkeypatch):
    pool = subject.LeasePool(SimpleNamespace(protocol=plan, completed_arms=set()))
    monkeypatch.setattr(pool, "_host_admission", lambda _: pytest.fail("bootstrap before RAM"))
    runner = SimpleNamespace(context=context(seed=389), disk_projection=lambda _: 0)
    assert pool.try_acquire(runner, "replay_R3") is None


def test_after_full251_complete_one_lease_blocks_any_second_worker(plan, monkeypatch):
    c = SimpleNamespace(protocol=plan, completed_arms={(251, "Full")})
    pool = subject.LeasePool(c)
    pool.leases = {0: object()}
    monkeypatch.setattr(pool, "_host_admission", lambda _: pytest.fail("cap before RAM"))
    assert pool.try_acquire(object(), "shard00") is None


@pytest.mark.parametrize("completed,stage,seed", [(False, "train", 251), (True, "replay_R3", 389),
                                                (True, "generate", 251), (True, "shard02", 389)])
def test_gpu0_runs_bootstrap_then_all_remaining_stages_serially(plan, tmp_path, monkeypatch,
                                                               completed, stage, seed):
    c = SimpleNamespace(protocol=plan, completed_arms={(251, "Full")} if completed else set(),
                        disk_gate=lambda _: None)
    pool = subject.LeasePool(c)
    monkeypatch.setattr(pool, "_host_admission", lambda _: True)
    monkeypatch.setattr(subject.parent, "inventory", lambda: [row(0), row(5)])
    monkeypatch.setattr(subject.parent, "TRAINING_ROOT", tmp_path / "training")
    runner = SimpleNamespace(context=context(seed=seed), disk_projection=lambda _: 0)
    observed, lease = pool.try_acquire(runner, stage)
    assert observed["index"] == 0 and set(pool.leases) == {0}
    lease.close()
    assert not pool.leases


def test_runtime_owns_eight_new_files_and_does_not_mutate_historical_verifiers():
    assert len(subject.FILES) == 8 and not any("handoff" in f for f in subject.FILES)
    assert subject.ALLOWED_GPUS == (0,) and subject.MAX_GPU_WORKERS == 1
    assert subject.parent is not subject.verifier.parent
    assert subject.runtime.LeasePool is subject.LeasePool
    assert subject.verifier.ROOT == subject.PARENT_ROOT
    assert subject.verifier.parent.checked_protocol is not subject.checked_protocol


@pytest.mark.parametrize("field,value", [
    ("max_gpu_workers", None), ("max_gpu_workers", 3), ("max_gpu_workers", 1.0),
    ("independent_total_worker_limit", None), ("total_worker_limit_removed", True),
    ("steady_gpu_indices", [5]), ("steady_max_gpu_workers", 2),
])
def test_protocol_rejects_broad_or_untyped_device_contract(plan, monkeypatch, field, value):
    monkeypatch.setattr(a.time_policy, "validate", lambda _: None)
    plan[field] = value
    with pytest.raises(a.AdmissionError, match="GPU0-only single-worker"):
        a.validate_plan(plan)


def test_policy_is_static_and_does_not_consult_mutable_checkpoint_state(plan, monkeypatch):
    monkeypatch.setattr(a.time_policy, "validate", lambda _: None)
    assert a.validate_plan(plan) is plan
    assert a.execution_policy_record() == a.execution_policy_record()
    assert plan["gpu_reservation_policy"]["lifetime_allocated_limit_bytes"] == 76 * 1024**3
    assert plan["gpu_reservation_policy"]["actual_boundary_free_reserve_bytes"] == 2 * 1024**3


def test_automatic_attempt_keeps_gpu0_scope_and_no_new_scientific_dose(tmp_path, monkeypatch):
    monkeypatch.setattr(subject, "entry", lambda p: dict(path=str(p), id="sealed"))
    monkeypatch.setattr(subject, "_capacity_wait_reference", lambda _: None)
    value = subject.authorization_body(parentroot=tmp_path, automatic=True)
    assert value["allowed_gpu_indices"] == [0]
    assert value["steady_gpu_indices"] == [0] and value["steady_max_gpu_workers"] == 1
    assert value["max_gpu_workers"] == value["independent_total_worker_limit"] == 1
    assert value["automatic_recovery_authorized"] is True
    assert value["unknown_feedback_retry_allowed"] is False
    assert value["new_sampling_or_optimizer_dose_authorized"] is False
