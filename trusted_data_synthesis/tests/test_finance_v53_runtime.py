"""Focused CPU contracts for native R3 routing, acceptance and fresh recovery."""

import importlib
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest

sys.path.insert(0, str(Path(__file__).parents[1] / "scripts"))
control = importlib.import_module("finqa_v53_controller")
admission, reservation = control.admission, control.reservation


def plan(tmp_path):
    return dict(
        id="V53_CPU", schema=control.PROTOCOL_SCHEMA, output_root=str(tmp_path),
        allowed_gpu_indices=list(admission.ALLOWED_GPUS),
        gpu_uuids=dict(admission.GPU_UUIDS), max_gpu_workers=None,
        independent_total_worker_limit=None, total_worker_limit_removed=True,
        max_workers_per_gpu=1, steady_gpu_indices=list(admission.ALLOWED_GPUS),
        steady_max_gpu_workers=None, effective_device_capacity=7,
        gpu_execution_policy=admission.execution_policy_record(),
        gpu_admission_policy=control.policy_record(),
        gpu_reservation_policy=control.reservation_policy_record(),
        host_admission_policy=control.host_policy_record(),
        host_ram_runtime_hard_gates_unchanged=True,
        time_policy=control.time_policy.record(), inheritance={"path": "inheritance"},
    )


def test_actual_registered_native_policy_retains_gpu_scope_and_hard_gates(tmp_path):
    registered = plan(tmp_path)
    assert admission.validate_plan(registered) is registered
    assert admission.ALLOWED_GPUS == (0, 1, 3, 4, 5, 6, 7)
    assert control.MAX_GPU_WORKERS is None and len(control.FILES) == 8
    assert reservation.PHASE_MINIMUM_FREE_GIB["replay_R3"] == 56
    assert reservation.FREE_RESERVE_BYTES == 2 * 1024**3
    assert reservation.ALLOCATED_LIMIT_BYTES == 76 * 1024**3
    assert control.parent is not control.verifier.parent
    assert control.verifier.parent.checked_protocol is not control.checked_protocol
    for gpu in range(8):
        row = dict(index=gpu, uuid=admission.GPU_UUIDS.get(str(gpu), "excluded"),
                   free_mib=56 * 1024, processes=[dict(pid=123, used_mib=1000)])
        assert admission.eligible_gpu(row, registered, "replay_R3") is (gpu != 2)
        row["free_mib"] -= 1
        assert not admission.eligible_gpu(row, registered, "replay_R3")


@pytest.mark.parametrize("stage", ["replay_R3", "train", "distribution", "generate"])
def test_actual_result_acceptance_distinguishes_native_r3_from_other_stages(
    tmp_path, monkeypatch, stage
):
    registered = plan(tmp_path)
    reference = {"path": str(tmp_path / stage / "reservation/result/record.json")}
    result = dict(context_id="same_point", gpu_index=4, gpu_uuid=admission.GPU_UUIDS["4"],
                  gpu_reservation=reference)
    native = stage == "replay_R3"
    reserved = dict(
        schema=registered["gpu_reservation_policy"]["schema"], protocol_id=registered["id"],
        context_id=result["context_id"], stage=stage, gpu_index=4, gpu_uuid=result["gpu_uuid"],
        all_passed=True, lifetime_peak_reset_calls=1,
        target_bytes=0 if native else 50 * 1024**3,
        warm_allocation_bytes=0 if native else 50 * 1024**3,
        anchor_bytes=0 if native else 2 * 1024**2,
        segment=None if native else {"bound": True},
        allocation_mode="native_demand" if native else "anchored_native_segment",
        native_demand_allocator_used=native,
        reservation_held_through_final_scientific_boundary=not native,
        original_empty_cache_unchanged=True, original_R3_source_and_backend_hash_unchanged=True,
    )
    monkeypatch.setattr(control, "_original_check_result", lambda *args: None)
    monkeypatch.setattr(control, "read_ref", lambda ref: reserved if ref == reference else {
        "context_inheritances": []})
    control.check_result(registered, stage, result)
    reserved["reservation_held_through_final_scientific_boundary"] = native
    with pytest.raises(Exception, match="native demand|adaptive reservation"):
        control.check_result(registered, stage, result)


def test_nested_worker_routing_preserves_original_context_and_uses_v53_resource_shell(monkeypatch):
    worker = importlib.import_module("finqa_v53_worker")
    assert worker.original.original is worker.cold
    assert worker.cold.reservation is reservation
    context = dict(id="unchanged", seed=389, arm="Full", step=1192, due_outer=True)
    calls = []
    monkeypatch.setattr(admission, "wait_for_pre_cuda_admission", lambda *args, **kwargs:
                        calls.append(kwargs) or "CPU_READY")
    fake = SimpleNamespace(require=control.require, publish=lambda *args: None)
    with worker.bound_execution(fake):
        with worker.original.bound_execution(fake):
            assert worker.cold.execution_context(context, {}) is context
            assert worker.cold.admission.wait_for_pre_cuda_admission("CPU") == "CPU_READY"
            assert calls[0]["context"] is context
            assert worker.cold.base.DeadlineStop is worker.DeadlineStop
    assert "training_stop_step" not in context


def test_automatic_protocol_keeps_latest_cursor_and_pinned_128_is_provenance(
    tmp_path, monkeypatch
):
    root = tmp_path / "root"
    attempt = root / "attempts/attempt0002"
    monkeypatch.setattr(control, "ROOT", root)
    preparation = dict(gpu_admission_policy=control.policy_record(),
                       host_admission_policy=control.host_policy_record(),
                       gpu_reservation_policy=control.reservation_policy_record())
    budget = dict(pending_sealed_feedback_episodes=700,
                  future_first_sampling_feedback_episodes=0,
                  remaining_new_feedback_episodes=0, remaining_endpoint_answers=1147)
    inherited = dict(parent_protocol={"path": "parent"}, parent_pause={"path": "failure"},
                     inherited_resource_wait_seconds=120, remaining_scientific_budget=budget,
                     context_inheritances=[dict(replay_resume={"inherited_response_count": 160})])
    monkeypatch.setattr(control, "checked_preparation", lambda: preparation)
    monkeypatch.setattr(control, "_additional_supervisor_wait", lambda _: 7)
    monkeypatch.setattr(control, "checked", lambda path:
                        inherited if path.parent.name == "inheritance" else {})
    monkeypatch.setattr(control, "read_ref", lambda _: dict(host_ram=control.parent.HOST_RAM))
    monkeypatch.setattr(control, "entry", lambda path: {"path": str(path)})
    initial = dict(completed_physical_updates=13112, remaining_physical_updates=298,
                   completed_outers=35, remaining_outers=1)
    value = control.protocol_body(attempt, {"id": "impl", "source_commit": "commit"},
                                  initial, at="CPU_TIME")
    assert value["initial_inherited_response_count"] == 128
    assert value["initial_remaining_response_count"] == 303
    assert value["initial_observed_response_count"] == 137
    assert value["initial_progress"]["remaining_optimizer_updates"] == 298
    assert value["initial_progress"]["remaining_endpoint_answers"] == 1147
    assert value["explicit_r3_native_checkpoint_recovery_authorized"] is False
    assert value["unknown_signal_automatic_retry_allowed"] is False
    assert value["inherited_resource_wait_seconds"] == 127
    assert inherited["context_inheritances"][0]["replay_resume"]["inherited_response_count"] == 160


def test_initialization_checks_actual_inheritance_before_protocol(tmp_path, monkeypatch):
    root, source = tmp_path / "new", tmp_path / "parent"
    monkeypatch.setattr(control, "ROOT", root)
    monkeypatch.setattr(control, "checked_implementation", lambda _: {"id": "impl"})
    monkeypatch.setattr(control, "checked_preparation", lambda: {"parent_root": str(source)})
    monkeypatch.setattr(control, "stopped_parent_protocol", lambda _: None)
    monkeypatch.setattr(control, "entry", lambda path: {"path": str(path)})
    published = {}
    monkeypatch.setattr(control, "publish", lambda path, body:
                        published.setdefault(str(path), body))
    def reject(*args, **kwargs):
        authority = published[kwargs["authorization_record"]["path"]]
        assert authority["explicit_r3_native_checkpoint_recovery_authorized"] is True
        assert authority["R3_warm_large_segment_reservation_disabled"] is True
        assert authority["initial_inherited_response_count"] == 128
        raise ValueError("same-point checkpoint mismatch")
    monkeypatch.setattr(control.inheritance, "initialize_authorized_recovery", reject)
    monkeypatch.setattr(control, "_finish_initialization", lambda *args:
                        pytest.fail("cannot publish protocol after rejected inheritance"))
    with pytest.raises(ValueError, match="same-point checkpoint"):
        control.initialize_authorized_recovery(root)
    assert str(root / "activation_registration/record.json") not in published


def test_supervisor_stop_before_launch_never_dispatches_or_retries(tmp_path):
    supervisor = importlib.import_module("finqa_v53_supervisor")
    fake = SimpleNamespace(require=control.require, ROOT=tmp_path)
    owner = supervisor.Supervisor(tmp_path, control=fake)
    owner.stopped = True
    with pytest.raises(supervisor._ExplicitStopBeforeLaunch):
        owner.launch(tmp_path, 1)


def test_automatic_attempt_rejects_unknown_failure_before_any_write(tmp_path, monkeypatch):
    root = tmp_path / "root"
    monkeypatch.setattr(control, "ROOT", root)
    monkeypatch.setattr(control.inheritance, "validate_safe_recovery", lambda _: {
        "allowed": False, "reason": "unknown signal"})
    monkeypatch.setattr(control.runtime, "clone_implementation", lambda *args:
                        pytest.fail("unknown failure cannot clone a new attempt"))
    with pytest.raises(Exception, match="no verified safe automatic boundary"):
        control.prepare_automatic(root / "attempts/attempt0002", parentroot=root)
