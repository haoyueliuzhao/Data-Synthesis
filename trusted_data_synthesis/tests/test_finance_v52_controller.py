"""CPU-only V52 pinned response121 authority and unchanged runtime contract."""

import importlib
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest

sys.path.insert(0, str(Path(__file__).parents[1] / "scripts"))
subject = importlib.import_module("finqa_v52_controller")
a, r = subject.admission, subject.reservation
GIB = 1024**3


@pytest.fixture
def plan(tmp_path):
    return dict(
        id="v52",
        output_root=str(tmp_path),
        schema=subject.PROTOCOL_SCHEMA,
        allowed_gpu_indices=list(a.ALLOWED_GPUS),
        gpu_uuids=dict(a.GPU_UUIDS),
        max_gpu_workers=None,
        independent_total_worker_limit=None,
        total_worker_limit_removed=True,
        max_workers_per_gpu=1,
        steady_gpu_indices=list(a.ALLOWED_GPUS),
        steady_max_gpu_workers=None,
        effective_device_capacity=7,
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


@pytest.mark.parametrize("gpu", [True, 0.0, 2, 8])
def test_every_other_device_or_ambiguous_index_is_rejected(plan, gpu):
    assert not a.device_scope_allows(gpu, "train", context())
    assert not a.eligible_gpu(row(gpu), plan, "train", context())


@pytest.mark.parametrize("state", ["INITIALIZING", "WAITING", "RUNNING", "DRAINING"])
def test_device_slots_count_every_lifecycle_state(plan, monkeypatch, state):
    pool = subject.LeasePool(SimpleNamespace(protocol=plan))
    pool.leases = {gpu: SimpleNamespace(lifecycle_state=state) for gpu in a.ALLOWED_GPUS}
    monkeypatch.setattr(pool, "_host_admission", lambda _: pytest.fail("cap before RAM"))
    assert pool.try_acquire(object(), "train") is None


def test_seven_unique_device_slots_gpu0_then_gpu6_without_independent_cap(plan, tmp_path, monkeypatch):
    control = SimpleNamespace(protocol=plan, disk_gate=lambda _: None)
    pool = subject.LeasePool(control)
    monkeypatch.setattr(pool, "_host_admission", lambda _: True)
    monkeypatch.setattr(subject.parent, "inventory", lambda: [row(gpu) for gpu in range(8)])
    monkeypatch.setattr(subject.parent, "TRAINING_ROOT", tmp_path / "training")
    runner = SimpleNamespace(context=context(), disk_projection=lambda _: 0)
    leases = [pool.try_acquire(runner, "shard00")[1] for _ in range(7)]
    assert tuple(lease.gpu for lease in leases) == subject.DISPATCH_ORDER
    assert pool.try_acquire(runner, "shard00") is None
    leases[0].close()
    _, replacement = pool.try_acquire(runner, "shard00")
    assert replacement.gpu == 0 and set(pool.leases) == set(a.ALLOWED_GPUS)
    for lease in leases[1:]:
        lease.close()
    replacement.close()
    assert not pool.leases


def test_shared_device_competition_requires_threshold_and_exact_uuid(plan):
    observed = dict(row(6), free_mib=56 * 1024, processes=[dict(pid=42, used_mib=1000)])
    assert a.eligible_gpu(observed, plan, "replay_R3", context())
    assert not a.eligible_gpu(dict(observed, free_mib=56 * 1024 - 1), plan, "replay_R3", context())
    assert not a.eligible_gpu(dict(observed, uuid="GPU-wrong"), plan, "replay_R3", context())


@pytest.mark.parametrize(
    "field,value",
    [
        ("max_gpu_workers", 2),
        ("max_gpu_workers", 1),
        ("max_gpu_workers", 3),
        ("max_gpu_workers", 2.0),
        ("independent_total_worker_limit", 2),
        ("total_worker_limit_removed", False),
        ("steady_gpu_indices", [0]),
        ("steady_max_gpu_workers", 1),
        ("max_workers_per_gpu", 2),
    ],
)
def test_protocol_rejects_broad_or_untyped_contract(plan, monkeypatch, field, value):
    monkeypatch.setattr(a.time_policy, "validate", lambda _: None)
    plan[field] = value
    with pytest.raises(a.AdmissionError, match="seven GPU slots"):
        a.validate_plan(plan)


def test_frozen_ownership_and_resource_math_do_not_change(plan, monkeypatch):
    monkeypatch.setattr(a.time_policy, "validate", lambda _: None)
    assert a.validate_plan(plan) is plan
    assert len(subject.FILES) == 8 and "finqa_v52_handoff.py" not in subject.FILES
    assert subject.PROTOCOL_SCHEMA == "v52_response121_supervised_protocol.v1"
    assert subject.ALLOWED_GPUS == (0, 1, 3, 4, 5, 6, 7) and subject.MAX_GPU_WORKERS is None
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
    assert value["allowed_gpu_indices"] == value["steady_gpu_indices"] == list(a.ALLOWED_GPUS)
    assert value["max_gpu_workers"] is value["independent_total_worker_limit"] is None
    assert value["total_worker_limit_removed"] is True
    assert value["resource_pool_without_independent_cap_authorized"] is True
    assert value["max_workers_per_gpu"] == 1
    assert value["automatic_recovery_authorized"] is True
    assert value["time_limits_removed"] is True
    assert value["unknown_feedback_retry_allowed"] is False
    assert value["new_sampling_or_optimizer_dose_authorized"] is False
    assert value["clean_handoff_authorized"] is False
    assert value["explicit_signal_checkpoint_recovery_authorized"] is (not automatic)
    assert value["known_failure_recovery_authorized"] is (not automatic)
    assert value["unknown_signal_automatic_retry_allowed"] is False
    assert value["prior_conditional_four_worker_ceiling_superseded"] is True
    assert value["initial_inherited_response_count"] == 121
    assert value["initial_remaining_response_count"] == 310
    assert value["initial_total_response_count"] == 431
    assert "inherited_response_count" not in value
    assert "remaining_response_count" not in value
    assert "total_response_count" not in value
    assert value["initial_response_checkpoint_id"] == subject.INITIAL_RESPONSE_CHECKPOINT_ID
    assert "resource_retirement_receipt" not in value


def test_stopped_parent_cannot_follow_an_automatic_attempt_or_another_protocol(monkeypatch):
    root = subject.STOPPED_PARENT_ROOT
    value = dict(
        id=subject.STOPPED_PARENT_PROTOCOL_ID,
        output_root=str(root),
        supervision_root=str(root),
        schema="v51_dual_gpu_two_worker_supervised_protocol.v1",
    )
    monkeypatch.setattr(subject, "checked", lambda _: value)
    assert subject.stopped_parent_protocol(root) is value
    with pytest.raises(Exception, match="pinned stopped V51 attempt"):
        subject.stopped_parent_protocol(root / "attempts/attempt0002")
    value["id"] = "changed"
    with pytest.raises(Exception, match="pinned stopped V51 owner"):
        subject.stopped_parent_protocol(root)


@pytest.mark.parametrize("accepted", [False, True])
def test_explicit_initialization_must_pass_inheritance_before_protocol(
    tmp_path, monkeypatch, accepted
):
    root, parentroot = tmp_path / "new", tmp_path / "stopped"
    events, published = [], {}
    implementation, inherited = {"id": "implementation"}, {"id": "inheritance"}
    monkeypatch.setattr(subject, "ROOT", root)
    monkeypatch.setattr(subject, "checked_implementation", lambda _: implementation)
    monkeypatch.setattr(subject, "checked_preparation", lambda: {"parent_root": str(parentroot)})
    monkeypatch.setattr(subject, "entry", lambda path: {"path": str(path)})
    monkeypatch.setattr(subject, "stopped_parent_protocol", lambda _: events.append("bound_parent"))
    monkeypatch.setattr(
        subject, "authorization_body", lambda **kwargs: {"automatic_attempt": kwargs["automatic"]}
    )
    monkeypatch.setattr(
        subject, "publish", lambda path, body: published.setdefault(str(path), body)
    )

    def inherit(target, source, *, authorization_record):
        assert target == root and source == parentroot
        assert authorization_record == {"path": str(root / "activation_authorization/record.json")}
        assert published[authorization_record["path"]]["automatic_attempt"] is False
        events.append("inheritance_gate")
        if not accepted:
            raise ValueError("checkpoint binding rejected")
        return inherited

    def finish(target, source_code, source_data):
        assert (target, source_code, source_data) == (root, implementation, inherited)
        events.append("finish_protocol")
        return {"id": "protocol"}

    monkeypatch.setattr(subject.inheritance, "initialize_authorized_recovery", inherit, raising=False)
    monkeypatch.setattr(subject, "_finish_initialization", finish)
    if accepted:
        assert subject.initialize_authorized_recovery(root) == {"id": "protocol"}
        assert events == ["bound_parent", "inheritance_gate", "finish_protocol"]
        activation = published[str(root / "activation_registration/record.json")]
        assert activation["handoff_claimed"] is False
        assert activation["scientific_controller_started"] is False
        assert activation["unknown_signal_automatic_retry_allowed"] is False
    else:
        with pytest.raises(ValueError, match="checkpoint binding rejected"):
            subject.initialize_authorized_recovery(root)
        assert events == ["bound_parent", "inheritance_gate"]
        assert str(root / "activation_registration/record.json") not in published


def test_initialization_cannot_reuse_an_existing_protocol(tmp_path, monkeypatch):
    root = tmp_path / "registered"
    (root / "protocol").mkdir(parents=True)
    (root / "protocol/record.json").touch()
    monkeypatch.setattr(subject, "ROOT", root)
    monkeypatch.setattr(subject, "checked_implementation", lambda _: pytest.fail("too late"))
    with pytest.raises(Exception, match="one explicit stopped-parent response121"):
        subject.initialize_authorized_recovery(root)


@pytest.mark.parametrize("cursor,replay_complete,remaining_updates", [(160, False, 298), (431, True, 170)])
def test_automatic_protocol_keeps_actual_budget_and_initial_cursor_as_provenance_only(
    tmp_path, monkeypatch, cursor, replay_complete, remaining_updates
):
    root = tmp_path / "supervised"
    attempt = root / "attempts/attempt0002"
    monkeypatch.setattr(subject, "ROOT", root)
    preparation = dict(
        gpu_admission_policy=subject.policy_record(),
        host_admission_policy=subject.host_policy_record(),
        gpu_reservation_policy=subject.reservation_policy_record(),
    )
    actual_resume = dict(inherited_response_count=cursor, total_responses=431)
    budget = dict(
        pending_sealed_feedback_episodes=0 if replay_complete else 700,
        future_first_sampling_feedback_episodes=0,
        remaining_new_feedback_episodes=0,
        remaining_endpoint_answers=1147,
    )
    inherited = dict(
        parent_protocol={"path": "parent/protocol"},
        parent_pause={"path": "parent/failure"},
        inherited_resource_wait_seconds=120,
        remaining_scientific_budget=budget,
        context_inheritances=[dict(replay_resume=actual_resume, replay_complete=replay_complete)],
    )
    monkeypatch.setattr(subject, "checked_preparation", lambda: preparation)
    monkeypatch.setattr(subject, "_additional_supervisor_wait", lambda _: 7)
    monkeypatch.setattr(
        subject, "checked", lambda path: inherited if path.parent.name == "inheritance" else {}
    )
    monkeypatch.setattr(subject, "read_ref", lambda _: dict(host_ram=subject.parent.HOST_RAM))
    monkeypatch.setattr(subject, "entry", lambda path: {"path": str(path)})
    initial = dict(
        completed_physical_updates=13410 - remaining_updates,
        remaining_physical_updates=remaining_updates,
        completed_outers=35 if not replay_complete else 36,
        remaining_outers=1 if not replay_complete else 0,
    )
    body = subject.protocol_body(
        attempt, {"id": "code", "source_commit": "commit"}, initial, at="CPU_TIME"
    )
    assert body["inheritance"] == {"path": str(attempt / "inheritance/record.json")}
    assert inherited["context_inheritances"][0]["replay_resume"] is actual_resume
    assert actual_resume["inherited_response_count"] == cursor
    assert body["initial_progress"]["remaining_optimizer_updates"] == remaining_updates
    for key, value in budget.items():
        assert body["initial_progress"][key] == value
    assert body["initial_inherited_response_count"] == 121
    assert body["initial_remaining_response_count"] == 310
    assert not any(key in body for key in ("inherited_response_count", "remaining_response_count"))
    assert body["manually_authorized_known_failure_recovery"] is False
    assert body["explicit_signal_checkpoint_recovery_authorized"] is False
    assert body["unknown_signal_automatic_retry_allowed"] is False
    assert body["inherited_resource_wait_seconds"] == 127


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
    endpoint = importlib.import_module("finqa_v52_evaluation")
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
