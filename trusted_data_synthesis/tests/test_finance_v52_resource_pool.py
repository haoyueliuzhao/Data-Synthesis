"""Narrow CPU checks for the newer seven-device/no-independent-cap consent."""

import importlib
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest

sys.path.insert(0, str(Path(__file__).parents[1] / "scripts"))
control = importlib.import_module("finqa_v52_controller")
admission = control.admission


def plan():
    return dict(
        allowed_gpu_indices=list(admission.ALLOWED_GPUS),
        gpu_uuids=dict(admission.GPU_UUIDS),
        max_gpu_workers=None,
        independent_total_worker_limit=None,
        total_worker_limit_removed=True,
        max_workers_per_gpu=1,
        steady_gpu_indices=list(admission.ALLOWED_GPUS),
        steady_max_gpu_workers=None,
        effective_device_capacity=7,
        gpu_execution_policy=admission.execution_policy_record(),
        gpu_admission_policy=control.policy_record(),
        gpu_reservation_policy=control.reservation_policy_record(),
        host_admission_policy=control.host_policy_record(),
        host_ram_runtime_hard_gates_unchanged=True,
        time_policy=control.time_policy.record(),
    )


@pytest.mark.parametrize("gpu", range(8))
def test_all_stages_exclude_gpu2_and_allow_exactly_the_other_seven_devices(gpu):
    for stage in admission.STAGES:
        assert admission.device_scope_allows(gpu, stage) is (gpu != 2)
    assert (str(gpu) in admission.GPU_UUIDS) is (gpu != 2)
    assert (str(gpu) in admission.CPU_AFFINITY) is (gpu != 2)


def test_null_is_explicit_no_independent_cap_but_not_a_missing_field():
    registered = plan()
    assert admission.validate_plan(registered) is registered
    for name in ("max_gpu_workers", "independent_total_worker_limit", "steady_max_gpu_workers"):
        missing = dict(registered)
        missing.pop(name)
        with pytest.raises(admission.AdmissionError, match="seven GPU slots"):
            admission.validate_plan(missing)
        with pytest.raises(admission.AdmissionError, match="seven GPU slots"):
            admission.validate_plan(dict(registered, **{name: 7}))


@pytest.mark.parametrize("automatic", [False, True])
def test_initial_and_auto_authority_keep_new_scope_without_expanding_science(monkeypatch, automatic):
    monkeypatch.setattr(control, "entry", lambda path: {"path": str(path), "id": "CPU"})
    monkeypatch.setattr(control, "_capacity_wait_reference", lambda _: None)
    value = control.authorization_body(parentroot=Path("/stopped"), automatic=automatic)
    assert value["allowed_gpu_indices"] == [0, 1, 3, 4, 5, 6, 7]
    assert value["max_gpu_workers"] is value["independent_total_worker_limit"] is None
    assert value["total_worker_limit_removed"] is True
    assert value["max_workers_per_gpu"] == 1 and value["effective_device_capacity"] == 7
    assert value["resource_pool_without_independent_cap_authorized"] is True
    assert value["new_sampling_or_optimizer_dose_authorized"] is False
    assert value["unknown_signal_automatic_retry_allowed"] is False
    assert value["explicit_signal_checkpoint_recovery_authorized"] is (not automatic)
    assert "取消并发上限限制" in value["user_instruction"]
    assert "除GPU2外均可使用" in value["user_consent"]
    assert control.ROOT.name == "signal_checkpoint_recovery_02"
    assert control.STOPPED_PARENT_ROOT.name == "dual_gpu0_gpu6_01"


def test_seven_unique_leases_allow_more_than_two_and_never_gpu2(tmp_path, monkeypatch):
    registered = plan()
    pool = control.LeasePool(SimpleNamespace(protocol=registered, disk_gate=lambda _: None))
    inventory = [
        dict(index=gpu, uuid=admission.GPU_UUIDS.get(str(gpu), "GPU2"), free_mib=80 * 1024, processes=[])
        for gpu in range(8)
    ]
    monkeypatch.setattr(pool, "_host_admission", lambda _: True)
    monkeypatch.setattr(control.parent, "inventory", lambda: inventory)
    monkeypatch.setattr(control.parent, "TRAINING_ROOT", tmp_path)
    runner = SimpleNamespace(context={}, disk_projection=lambda _: 0)
    leases = [pool.try_acquire(runner, "train")[1] for _ in range(7)]
    assert tuple(lease.gpu for lease in leases) == (0, 6, 3, 4, 5, 1, 7)
    assert len(pool.leases) == 7 and 2 not in pool.leases
    assert pool.try_acquire(runner, "train") is None
    for lease in leases:
        lease.close()


@pytest.mark.parametrize("lifecycle", ["INITIALIZING", "WAITING", "RUNNING", "DRAINING"])
def test_lifecycle_still_occupies_each_device_slot(monkeypatch, lifecycle):
    pool = control.LeasePool(SimpleNamespace(protocol=plan()))
    pool.leases = {gpu: SimpleNamespace(lifecycle_state=lifecycle) for gpu in admission.ALLOWED_GPUS}
    monkeypatch.setattr(pool, "_host_admission", lambda _: pytest.fail("no unleased device"))
    assert pool.try_acquire(object(), "train") is None


def test_resource_gates_and_adaptive_reservation_are_unchanged():
    value = control.reservation.policy_record()
    assert value["independent_total_worker_limit"] is None
    assert value["total_worker_limit_removed"] is True
    assert value["target_cap_bytes"] == 72 * 1024**3
    assert value["lifetime_allocated_limit_bytes"] == 76 * 1024**3
    assert value["actual_boundary_free_reserve_bytes"] == 2 * 1024**3
    assert admission.minimum_free_mib("replay_R3") == 56 * 1024
    assert admission.HOST_RESERVE_BYTES == 96 * 1024**3
