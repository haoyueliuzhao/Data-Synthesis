"""CPU-only five-slot routing, actual CLI parsing and unchanged admission gates."""

import importlib
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest
import test_finance_v43_consumers as v43_tests

sys.path.insert(0, str(Path(__file__).parents[1] / "scripts"))
admission = importlib.import_module("finqa_v44_admission")
worker = importlib.import_module("finqa_v44_worker")
evaluation = importlib.import_module("finqa_v44_evaluation")


def require(value, message):
    if not value:
        raise ValueError(message)


@pytest.fixture
def resource(tmp_path):
    f = v43_tests.resource.__wrapped__(tmp_path)
    plan = f.kwargs["plan"]
    plan.update(max_gpu_workers=5, max_workers_per_gpu=1)
    plan["gpu_admission_policy"]["admission"][
        "maximum_total_workers_including_initializing_and_draining"
    ] = 5
    return f


def test_five_slots_keep_actual_shared_gpu_and_null_deadline(resource):
    f = resource
    assert admission.wait_for_pre_cuda_admission(**f.kwargs) is f.ready
    assert f.status()["deadline_epoch"] is None
    assert f.status()["minimum_free_mib"] == 32 * 1024
    assert f.status()["rss_limit_bytes"] == 192 * 1024**3
    assert f.status()["host_available_reserve_bytes"] == 96 * 1024**3
    assert f.status()["gpu"]["processes"]


@pytest.mark.parametrize("capacity", [4, 6])
def test_capacity_mismatch_fails_before_admission(resource, capacity):
    resource.kwargs["plan"]["max_gpu_workers"] = capacity
    with pytest.raises(ValueError, match="five-slot"):
        admission.wait_for_pre_cuda_admission(**resource.kwargs)


def test_stale_embedded_four_slot_metadata_is_rejected(resource):
    resource.kwargs["plan"]["gpu_admission_policy"]["admission"][
        "maximum_total_workers_including_initializing_and_draining"
    ] = 4
    with pytest.raises(ValueError, match="five-slot"):
        admission.validate_plan(resource.kwargs["plan"])


def test_evaluation_accepts_exact_controller_generate_argv(monkeypatch, tmp_path):
    calls = []
    monkeypatch.setattr(
        evaluation, "run", lambda *args: calls.append(args) or dict(status="MOCK", id="mock")
    )
    evaluation.main(
        [
            "generate",
            "--stage",
            "generate",
            "--root",
            str(tmp_path),
            "--seed",
            "389",
            "--arm",
            "full",
            "--gpu-index",
            "5",
        ]
    )
    assert calls == [(tmp_path, 389, "full", 5, None)]


def test_score_api_routes_original_barrier_without_scoring(resource, monkeypatch, tmp_path):
    control = SimpleNamespace(
        checked_protocol=lambda root: resource.kwargs["plan"], require=require
    )
    calls = []
    old_controller = evaluation.original._controller
    monkeypatch.setattr(evaluation, "_controller", lambda: control)
    monkeypatch.setattr(evaluation, "_checked_entry", lambda *args: None)

    def original_score(root):
        assert evaluation.original._controller() is control
        assert evaluation.original.admission is admission
        calls.append(root)
        return dict(status="MOCK_NOT_SCORED", id="mock")

    monkeypatch.setattr(evaluation.original, "score", original_score)
    assert evaluation.score(tmp_path)["status"] == "MOCK_NOT_SCORED"
    evaluation.main(["score", "--root", str(tmp_path)])
    assert calls == [tmp_path, tmp_path] and evaluation.original._controller is old_controller


def test_worker_routes_new_inheritance_without_modifying_original_context(
    resource, monkeypatch, tmp_path
):
    control = SimpleNamespace(
        checked_protocol=lambda root: resource.kwargs["plan"], require=require
    )
    old = {
        key: getattr(worker.original, key)
        for key in ("_controller", "inheritance", "admission", "task_overlay")
    }
    monkeypatch.setattr(worker, "_controller", lambda: control)
    monkeypatch.setattr(worker, "_checked_entry", lambda *args: None)

    def delegate(root, context, stage, gpu, deadline):
        assert worker.original._controller() is control
        assert worker.original.inheritance is worker.inheritance
        assert worker.original.admission is admission
        assert deadline is None and stage == "shard03"
        return dict(status="MOCK", context=context)

    monkeypatch.setattr(worker.original, "run", delegate)
    result = worker.run(tmp_path, tmp_path / "unchanged_context", "shard03", 5)
    assert result["context"] == tmp_path / "unchanged_context"
    assert all(getattr(worker.original, key) is value for key, value in old.items())


def test_class_window_uses_v44_inheritance_and_keeps_four_math_shards(resource, monkeypatch):
    control = SimpleNamespace(require=require)
    context = dict(id="actual")
    binding = dict(
        schema="v43_same_point_partial_task_cache_union.v1",
        original_context_id="actual",
        allowed_new_stages=["shard03"],
    )
    calls = []
    monkeypatch.setattr(
        worker.inheritance, "task_cache_overlay_binding", lambda *a: calls.append(a) or binding
    )
    with worker.bound_execution(control):
        assert (
            worker.original.task_overlay.validate_class_window(
                "new", context, resource.kwargs["plan"], "shard03", None, control=control
            )
            is binding
        )
    assert len(calls) == 1 and worker.original.task_overlay.SHARDS == (
        "shard00",
        "shard01",
        "shard02",
        "shard03",
    )


def test_unsealed_entry_paths_are_not_faked(tmp_path):
    control = SimpleNamespace(
        require=require, __file__=str(tmp_path / "implementation/finqa_v44_controller.py")
    )
    with pytest.raises(ValueError, match="actual"):
        worker._checked_entry(tmp_path, control)
    with pytest.raises(ValueError, match="actual"):
        evaluation._checked_entry(tmp_path, control)
