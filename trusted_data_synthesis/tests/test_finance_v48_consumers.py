"""CPU-only early reservation, honest initialized-CUDA hooks and original maths."""

import importlib
import inspect
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest
import test_finance_v43_evaluation as legacy_evaluation_tests

sys.path.insert(0, str(Path(__file__).parents[1] / "scripts"))
worker = importlib.import_module("finqa_v48_worker")
evaluation = importlib.import_module("finqa_v48_evaluation")
admission = importlib.import_module("finqa_v48_admission")
control_module = importlib.import_module("finqa_v48_controller")


def require(condition, message):
    if not condition:
        raise ValueError(message)


def test_actual_cold_module_and_nested_identity_context_replace_old_pilot(monkeypatch):
    assert worker.original.original is worker.cold
    assert Path(worker.cold.__file__).name == "finqa_v48_cold_worker.py"
    context = dict(id="original", seed=389, arm="Full", step=298, due_outer=True)
    before = worker.cold.execution_context
    calls = []
    control = SimpleNamespace(require=require, publish=lambda *args: None)
    monkeypatch.setattr(
        admission,
        "wait_for_pre_cuda_admission",
        lambda *args, **kwargs: calls.append(kwargs) or "CPU_READY",
    )
    with worker.bound_execution(control):
        assert worker.original.policy is admission
        with worker.original.bound_execution(control):
            assert worker.cold.execution_context(context, {}) is context
            assert worker.cold.admission.wait_for_pre_cuda_admission("CPU") == "CPU_READY"
            assert calls[0]["context"] is context
            assert worker.cold.base.DeadlineStop is worker.DeadlineStop
            assert worker.cold.base.ResourceEvents is worker.ResourceEvents
    assert worker.cold.execution_context is before
    assert "training_stop_step" not in context


def test_cold_source_reserves_before_loading_and_never_performs_old_reset():
    source = inspect.getsource(worker.cold._run)
    assert source.index("memory_reservation.start") < source.index("bundle.context.load_context")
    assert source.index("bundle.context.load_context") < source.index("verify_before_model_load")
    assert "reset_peak_memory_stats" not in source
    assert worker.cold.STAGES[:4] == ("shard00", "shard01", "shard02", "shard03")


def test_unsealed_consumer_entries_are_rejected(tmp_path):
    control = SimpleNamespace(
        require=require, __file__=str(tmp_path / "implementation/finqa_v48_controller.py")
    )
    with pytest.raises(ValueError, match="actual new seal"):
        worker._checked_entry(tmp_path, control)
    with pytest.raises(ValueError, match="sealed V48"):
        evaluation._checked_entry(tmp_path, control)


@pytest.fixture
def endpoint(tmp_path, monkeypatch):
    monkeypatch.setattr(legacy_evaluation_tests, "subject", evaluation)
    monkeypatch.setattr(evaluation, "policy", admission.legacy_policy)
    f = legacy_evaluation_tests.endpoint.__wrapped__(tmp_path, monkeypatch)
    monkeypatch.setattr(evaluation, "policy", admission)
    f.plan.update(
        gpu_admission_policy=admission.gpu_policy_record(),
        gpu_reservation_policy=admission.reservation_policy_record(),
        host_admission_policy=admission.host_policy_record(),
        host_ram_runtime_hard_gates_unchanged=True,
        max_gpu_workers=None,
        independent_total_worker_limit=None,
        total_worker_limit_removed=True,
        max_workers_per_gpu=1,
    )
    f.control.__file__ = str(tmp_path / "implementation/finqa_v48_controller.py")
    monkeypatch.setattr(
        evaluation, "__file__", str(tmp_path / "implementation/finqa_v48_evaluation.py")
    )
    monkeypatch.setattr(
        admission, "__file__", str(tmp_path / "implementation/finqa_v48_admission.py")
    )
    monkeypatch.setattr(
        evaluation.reservation,
        "__file__",
        str(tmp_path / "implementation/finqa_v48_reservation.py"),
    )
    f.control.inventory = lambda: [f.source_row]

    class Reservation:
        def __init__(
            self,
            torch,
            directory,
            plan,
            context_id,
            stage,
            gpu_index,
            *,
            control,
            stop_requested=lambda: False,
        ):
            self.torch, self.directory = torch, Path(directory)
            self.context_id, self.stage, self.gpu_index = context_id, stage, gpu_index
            self.started = False

        def start(self, minimum):
            assert minimum == 24 * 1024**3 and not self.torch.cuda.is_initialized()
            self.torch.cuda.reset_peak_memory_stats()
            self.started = True
            f.calls.append(("reserve_before_model", minimum))
            return f.publish(
                self.directory / "reservation/admission/record.json",
                dict(cuda_initialized=True, lifetime_peak_reset_calls=1),
            )

        def verify_before_model_load(self):
            assert self.started and self.torch.cuda.is_initialized() and f.state.resets == 1
            assert not any(call[0] == "original_model_load" for call in f.calls)
            f.calls.append(("verify_existing_reservation",))

        def mark_model_load_started(self):
            self.verify_before_model_load()
            f.calls.append(("model_load_started",))

        def report(self):
            assert self.started and f.state.resets == 1
            return f.publish(
                self.directory / "reservation/result/record.json",
                dict(status="COMPLETE", all_passed=True, lifetime_peak_reset_calls=1),
            )

        def close(self):
            f.calls.append(("reservation_closed",))

        def __enter__(self):
            return self

        def __exit__(self, *_args):
            self.close()

    monkeypatch.setattr(evaluation.reservation, "Reservation", Reservation)
    return f


def test_original_endpoint_generation_has_one_reset_and_two_honest_post_cuda_checks(endpoint):
    f = endpoint
    result = evaluation.run(f.root, 389, "c_only", 6, None)
    assert result["status"] == "COMPLETE" and f.state.resets == 1
    assert result["minimum_free_mib"] == 24 * 1024
    assert result["actual_response_calls"] == 1
    assert result["gpu_reservation"]["path"].endswith("reservation/result/record.json")
    assert f.science == f.before
    assert len([call for call in f.calls if call[0] == "admission"]) == 1
    assert len([call for call in f.calls if call[0] == "original_generate"]) == 1
    assert len([call for call in f.calls if call[0] == "original_model_load"]) == 1
    labels = [call[0] for call in f.calls]
    assert labels.index("reserve_before_model") < labels.index("original_model_load")
    assert labels[-1] == "reservation_closed"
    import json

    for index in (1, 2):
        path = (
            f.root
            / "evaluations/seed389_c_only/generate/post_cuda_rechecks"
            / f"check{index:04d}/record.json"
        )
        value = json.loads(path.read_bytes())
        assert value["cuda_initialized"] is True
        assert value["lifetime_peak_reset_performed"] is False
    assert f.final.load_final_provider is f.original_loader
    assert f.final.eligible_gpu is f.original_eligible


def test_numeric_deadline_cannot_initialize_reservation(endpoint):
    with pytest.raises(ValueError, match="unexpected wall-clock"):
        evaluation.run(endpoint.root, 389, "c_only", 6, 1e300)
    assert not endpoint.calls and endpoint.state.resets == 0


def test_formal_reservation_policy_evidence_passes_unchanged_strict_reader():
    value = control_module.reservation_policy_record()
    assert value["evidence_refs"] and all("id" in ref for ref in value["evidence_refs"])
    assert value["cross_stage_or_recovery_permanent_exclusivity_claimed"] is False
