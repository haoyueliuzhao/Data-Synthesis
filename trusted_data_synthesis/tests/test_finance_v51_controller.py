"""CPU-only V51 exact-device, two-lifetime-slot and clean activation checks."""

import importlib
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest

sys.path.insert(0, str(Path(__file__).parents[1] / "scripts"))
subject = importlib.import_module("finqa_v51_controller")
a, r = subject.admission, subject.reservation
GIB = 1024**3


@pytest.fixture
def plan(tmp_path):
    return dict(
        id="v51",
        output_root=str(tmp_path),
        schema=subject.PROTOCOL_SCHEMA,
        allowed_gpu_indices=[0, 6],
        gpu_uuids=dict(a.GPU_UUIDS),
        max_gpu_workers=2,
        independent_total_worker_limit=2,
        total_worker_limit_removed=False,
        max_workers_per_gpu=1,
        steady_gpu_indices=[0, 6],
        steady_max_gpu_workers=2,
        gpu_execution_policy=a.execution_policy_record(),
        host_admission_policy=subject.host_policy_record(),
        gpu_admission_policy=subject.policy_record(),
        gpu_reservation_policy=subject.reservation_policy_record(),
        host_ram_runtime_hard_gates_unchanged=True,
    )


def row(gpu):
    return dict(
        index=gpu,
        uuid=a.GPU_UUIDS.get(str(gpu), "GPU-forbidden"),
        free_mib=80 * 1024,
        processes=[],
    )


def context():
    return dict(
        seed=389, arm="Full", step=1192, due_outer=True, feedback=dict(mode="first_sampling")
    )


@pytest.mark.parametrize("gpu", [0, 6])
@pytest.mark.parametrize("stage", a.STAGES)
def test_both_registered_devices_accept_all_original_stages(plan, gpu, stage):
    assert a.eligible_gpu(row(gpu), plan, stage, context())


@pytest.mark.parametrize("gpu", [True, 0.0, 1, 2, 3, 4, 5, 7])
def test_every_other_device_or_ambiguous_index_is_rejected(plan, gpu):
    assert not a.device_scope_allows(gpu, "train", context())
    assert not a.eligible_gpu(row(gpu), plan, "train", context())


@pytest.mark.parametrize("state", ["INITIALIZING", "WAITING", "RUNNING", "DRAINING"])
def test_two_slots_count_every_lifecycle_state(plan, monkeypatch, state):
    pool = subject.LeasePool(SimpleNamespace(protocol=plan))
    pool.leases = {gpu: SimpleNamespace(lifecycle_state=state) for gpu in (0, 6)}
    monkeypatch.setattr(pool, "_host_admission", lambda _: pytest.fail("cap before RAM"))
    assert pool.try_acquire(object(), "train") is None


def test_gpu0_then_gpu6_and_never_a_third_worker(plan, tmp_path, monkeypatch):
    control = SimpleNamespace(protocol=plan, disk_gate=lambda _: None)
    pool = subject.LeasePool(control)
    monkeypatch.setattr(pool, "_host_admission", lambda _: True)
    monkeypatch.setattr(subject.parent, "inventory", lambda: [row(5), row(6), row(0)])
    monkeypatch.setattr(subject.parent, "TRAINING_ROOT", tmp_path / "training")
    runner = SimpleNamespace(context=context(), disk_projection=lambda _: 0)
    _, first = pool.try_acquire(runner, "shard00")
    _, second = pool.try_acquire(runner, "shard01")
    assert (first.gpu, second.gpu) == (0, 6)
    assert pool.try_acquire(runner, "shard02") is None
    first.close()
    _, third = pool.try_acquire(runner, "shard02")
    assert third.gpu == 0 and set(pool.leases) == {0, 6}
    second.close()
    third.close()
    assert not pool.leases


def test_shared_device_competition_requires_threshold_and_exact_uuid(plan):
    observed = dict(row(6), free_mib=56 * 1024, processes=[dict(pid=42, used_mib=1000)])
    assert a.eligible_gpu(observed, plan, "replay_R3", context())
    assert not a.eligible_gpu(dict(observed, free_mib=56 * 1024 - 1), plan, "replay_R3", context())
    assert not a.eligible_gpu(dict(observed, uuid="GPU-wrong"), plan, "replay_R3", context())


@pytest.mark.parametrize(
    "field,value",
    [
        ("max_gpu_workers", None),
        ("max_gpu_workers", 1),
        ("max_gpu_workers", 3),
        ("max_gpu_workers", 2.0),
        ("independent_total_worker_limit", None),
        ("total_worker_limit_removed", True),
        ("steady_gpu_indices", [0]),
        ("steady_max_gpu_workers", 1),
        ("max_workers_per_gpu", 2),
    ],
)
def test_protocol_rejects_broad_or_untyped_contract(plan, monkeypatch, field, value):
    monkeypatch.setattr(a.time_policy, "validate", lambda _: None)
    plan[field] = value
    with pytest.raises(a.AdmissionError, match="GPU0/GPU6 two-worker"):
        a.validate_plan(plan)


def test_frozen_ownership_and_resource_math_do_not_change(plan, monkeypatch):
    monkeypatch.setattr(a.time_policy, "validate", lambda _: None)
    assert a.validate_plan(plan) is plan
    assert len(subject.FILES) == 9 and "finqa_v51_handoff.py" in subject.FILES
    assert subject.ALLOWED_GPUS == (0, 6) and subject.MAX_GPU_WORKERS == 2
    assert subject.runtime.LeasePool is subject.LeasePool
    assert subject.parent is not subject.verifier.parent
    assert subject.verifier.ROOT == subject.PARENT_ROOT
    assert subject.verifier.parent.checked_protocol is not subject.checked_protocol
    assert r.policy_record()["target_cap_bytes"] == 72 * GIB
    assert r.policy_record()["lifetime_allocated_limit_bytes"] == 76 * GIB
    assert r.policy_record()["actual_boundary_free_reserve_bytes"] == 2 * GIB
    assert r.target_bytes(54 * GIB, 26 * GIB, "train") == 50 * GIB
    assert r.target_bytes(79 * GIB, 26 * GIB, "train") == 72 * GIB
    assert r.target_bytes(79 * GIB, 56 * GIB, "replay_R3") == 71 * GIB
    assert a.execution_policy_record()["completed_bootstrap_is_read_only"] is True
    assert not hasattr(a, "bootstrap_stage_allows")


@pytest.mark.parametrize("automatic", [False, True])
def test_authority_and_auto_recovery_keep_scope_and_scientific_dose(
    tmp_path, monkeypatch, automatic
):
    monkeypatch.setattr(subject, "entry", lambda p: dict(path=str(p), id="sealed"))
    monkeypatch.setattr(subject, "_capacity_wait_reference", lambda _: None)
    value = subject.authorization_body(parentroot=tmp_path, automatic=automatic)
    assert value["allowed_gpu_indices"] == value["steady_gpu_indices"] == [0, 6]
    assert value["max_gpu_workers"] == value["independent_total_worker_limit"] == 2
    assert value["max_workers_per_gpu"] == 1
    assert value["automatic_recovery_authorized"] is True
    assert value["time_limits_removed"] is True
    assert value["unknown_feedback_retry_allowed"] is False
    assert value["new_sampling_or_optimizer_dose_authorized"] is False
    assert value["clean_handoff_authorized"] is (not automatic)
    assert "resource_retirement_receipt" not in value


def test_live_parent_cannot_follow_an_automatic_attempt_or_another_protocol(monkeypatch):
    root = subject.LIVE_PARENT_ROOT
    value = dict(
        id=subject.LIVE_PARENT_PROTOCOL_ID,
        output_root=str(root),
        supervision_root=str(root),
        schema="v50_single_gpu0_supervised_protocol.v1",
    )
    monkeypatch.setattr(subject, "checked", lambda _: value)
    assert subject.live_parent_protocol(root) is value
    with pytest.raises(Exception, match="pinned V50 attempt"):
        subject.live_parent_protocol(root / "attempts/attempt0002")
    value["id"] = "changed"
    with pytest.raises(Exception, match="pinned V50 owner"):
        subject.live_parent_protocol(root)


def test_missing_full251_completed_state_cannot_relaunch_bootstrap(monkeypatch):
    monkeypatch.setattr(
        subject.runtime.Controller,
        "__init__",
        lambda self, root: setattr(self, "completed_arms", set()),
    )
    with pytest.raises(Exception, match="completed Full251 bootstrap"):
        subject.Controller()


@pytest.mark.parametrize("gpu", [0, 6])
def test_endpoint_post_cuda_checks_accept_both_devices_without_new_reservation(
    plan, tmp_path, monkeypatch, gpu
):
    endpoint = importlib.import_module("finqa_v51_evaluation")
    monkeypatch.setattr(a.time_policy, "validate", lambda _: None)
    records, verified = [], []
    original = object()
    final = SimpleNamespace(
        eligible_gpu=original,
        torch=SimpleNamespace(cuda=SimpleNamespace(is_initialized=lambda: True)),
    )
    control = SimpleNamespace(
        require=subject.require,
        inventory=lambda: [row(gpu)],
        process_memory=lambda _: dict(rss_bytes=GIB, peak_rss_bytes=GIB),
        host_memory=lambda: dict(available_bytes=300 * GIB),
        publish=lambda p, body: records.append(body),
        now=lambda: "CPU_TIME",
        birth=lambda _: "birth",
        entry=lambda p: dict(path=str(p)),
    )
    owner = SimpleNamespace(verify_before_model_load=lambda: verified.append(True))
    with endpoint.endpoint_gpu_policy(
        final,
        plan,
        gpu,
        control,
        SimpleNamespace(requested=False),
        None,
        directory=tmp_path,
        context_id="context",
        reservation_owner=owner,
    ):
        assert final.eligible_gpu({}, gpu, [])["index"] == gpu
        assert final.eligible_gpu({}, gpu, [])["index"] == gpu
    assert final.eligible_gpu is original
    assert len(verified) == len(records) == 2
    assert all(
        record["gpu_index"] == gpu and not record["lifetime_peak_reset_performed"]
        for record in records
    )
