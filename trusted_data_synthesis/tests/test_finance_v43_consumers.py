"""CPU-only null deadlines, same-point task unions and ordered response recovery."""

import copy
import importlib
import json
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest
import test_finance_v40_replay as old_replay
import test_finance_v41_admission as old_admission
import test_finance_v42_task_overlay as old_tasks
import torch

sys.path.insert(0, str(Path(__file__).parents[1] / "scripts"))
admission = importlib.import_module("finqa_v43_admission")
time_policy = importlib.import_module("finqa_v43_time_policy")
tasks = importlib.import_module("finqa_v43_task_overlay")
replay = importlib.import_module("finqa_v43_replay")


@pytest.fixture
def resource(tmp_path):
    f = old_admission.admission.__wrapped__(tmp_path)
    f.kwargs["plan"]["time_policy"] = time_policy.record()
    f.kwargs["deadline_epoch"] = None
    return f


def test_shared_admission_has_real_null_deadline_and_continuing_wait_accounting(resource):
    f = resource
    f.ready["free_mib"] = 1

    def sleep(seconds):
        f.clock.sleep(200000 + seconds)
        f.ready["free_mib"] = 32 * 1024

    f.kwargs["sleep"] = sleep
    assert admission.wait_for_pre_cuda_admission(**f.kwargs) is f.ready
    status = f.status()
    assert status["deadline_epoch"] is None and status["waiting_seconds"] > 200000
    assert status["wallclock_limits_removed"] is True
    assert status["gpu"]["processes"] == [dict(pid=42, used_memory_mib="12000")]


@pytest.mark.parametrize("value", [0, 1e12, float("inf"), float("nan")])
def test_nonnull_deadline_sentinels_rejected(resource, value):
    resource.kwargs["deadline_epoch"] = value
    with pytest.raises(ValueError, match="actual null deadline"):
        admission.wait_for_pre_cuda_admission(**resource.kwargs)


@pytest.mark.parametrize("kind", ["ram", "rss", "cuda", "uuid", "stop"])
def test_no_deadline_does_not_relax_resource_identity_or_stop_gates(resource, kind):
    f = resource
    if kind == "ram":
        f.available = 95 * admission.GIB
    elif kind == "rss":
        f.peak_rss = 193 * admission.GIB
    elif kind == "cuda":
        f.initialized = True
    elif kind == "uuid":
        f.ready["uuid"] = "changed"
    else:
        f.stopped = True
    with pytest.raises((ValueError, RuntimeError)):
        admission.wait_for_pre_cuda_admission(**f.kwargs)


@pytest.fixture(scope="module")
def task_data(tmp_path_factory):
    return old_tasks.data.__wrapped__(tmp_path_factory)


@pytest.fixture
def union(task_data, tmp_path):
    f = old_tasks.overlay.__wrapped__(task_data, tmp_path)
    task_plan_path = tmp_path / "task_plan/record.json"
    task_plan_path.parent.mkdir(parents=True)
    task_plan_path.write_text(json.dumps(task_data.plan))
    reference = old_tasks.contexts.entry(task_plan_path)
    f.context["task_plan"] = reference
    f.binding.update(
        schema=tasks.SCHEMA,
        task_ids=task_data.plan["task_ids"],
        task_plan=reference,
        task_records=[
            dict(row, cache_root=str(f.parent_root)) for row in f.binding["parent_records"]
        ],
        cache_sources=[dict(cache_root=str(f.parent_root), task_ids=f.parent_ids)],
    )
    control = SimpleNamespace(
        **vars(old_tasks.CONTROL), read_ref=lambda ref: old_tasks.contexts.checked(ref["path"])
    )
    bundle = SimpleNamespace(
        context=old_tasks.contexts, original_cache=old_tasks.original, rt=task_data.rt
    )

    def build(stage, *, directory=None, binding=None):
        parent = old_tasks.contexts.ProductionTaskCache(
            f.parent_root,
            task_data.binding,
            task_data.plan,
            task_data.spec,
            task_data.rt,
            original_cache_module=old_tasks.original,
        )
        return tasks.build_overlay(
            parent,
            f.context,
            directory or f.directory,
            stage,
            binding or f.binding,
            bundle,
            control=control,
        )

    f.build = build
    return f


def test_second_attempt_inherits_all_complete_task_sources_without_recomputation(union):
    f = union
    first = f.build("shard01")
    completed = [
        task for task in first.plan["assignments"][1]["task_ids"] if task not in f.parent_ids
    ][:4]
    for task in completed:
        first.commit(task, old_tasks.values(first.task(task)["index"]))
    next_dir = f.directory.parent / "next_attempt"
    binding = copy.deepcopy(f.binding)
    parent_set = set(f.parent_ids) | set(completed)
    binding["parent_task_ids"] = [t for t in f.data.plan["task_ids"] if t in parent_set]
    binding["local_task_ids"] = [t for t in f.data.plan["task_ids"] if t not in parent_set]
    binding["local_cache_root"] = str(next_dir / "task_cache")
    binding["cache_sources"].append(dict(cache_root=str(first.root), task_ids=completed))
    records = {row["task_id"]: row for row in binding["task_records"]}
    for task in completed:
        path = first.directory(task)
        record = old_tasks.contexts.checked(path / "record.json")
        records[task] = dict(
            task_id=task,
            cache_root=str(first.root),
            record=old_tasks.contexts.entry(path / "record.json"),
            gradient=dict(
                path=str(path / "gradient.pt"),
                sha256=record["gradient_sha256"],
                bytes=record["gradient_bytes"],
            ),
            record_file_identity=tasks.complete_view._identity(path / "record.json"),
            gradient_file_identity=tasks.complete_view._identity(path / "gradient.pt"),
        )
    binding["task_records"] = [records[t] for t in binding["parent_task_ids"]]
    before = old_tasks.hashes(f.parent_root), old_tasks.hashes(first.root)
    new_calls = []
    for stage in binding["allowed_new_stages"]:
        cache = f.build(stage, directory=next_dir, binding=binding)
        for task in cache.plan["assignments"][int(stage[-2:])]["task_ids"]:
            if cache.has(task):
                continue
            cache.commit(task, old_tasks.values(cache.task(task)["index"]))
            new_calls.append(task)
    assert len(new_calls) == 463 and not set(new_calls) & parent_set
    merged = f.build("virtual_point", directory=next_dir, binding=binding).assemble()
    assert list(merged) == f.data.plan["task_ids"]
    assert all(
        torch.equal(merged[t]["z0"]["weight"], old_tasks.values(i)["z0"]["weight"])
        for i, t in enumerate(f.data.plan["task_ids"])
    )
    assert (old_tasks.hashes(f.parent_root), old_tasks.hashes(first.root)) == before


def test_partial_union_cannot_fill_missing_tasks_or_write_parent(union):
    cache = union.build("shard01")
    with pytest.raises(ValueError, match="dispatched missing"):
        cache.commit(union.parent_ids[0], old_tasks.values(0))
    with pytest.raises(ValueError, match="full original task population"):
        union.build("virtual_point").assemble()


@pytest.mark.parametrize("mutation", ["owner", "point", "order", "dose"])
def test_changed_task_union_binding_rejected(union, mutation):
    f = union
    if mutation == "owner":
        f.binding["task_records"][0]["cache_root"] = "/tmp/not-owner"
    elif mutation == "point":
        f.binding["original_context_id"] = "another-point"
    elif mutation == "order":
        f.binding["task_ids"] = list(reversed(f.binding["task_ids"]))
    else:
        f.binding["local_task_ids"] = f.binding["local_task_ids"][:-1]
    with pytest.raises(ValueError):
        f.build("shard01")


@pytest.fixture(scope="module")
def response_prefix(tmp_path_factory):
    return old_replay.prefix.__wrapped__(tmp_path_factory)


@pytest.fixture
def response(response_prefix, tmp_path):
    f = old_replay.continuation.__wrapped__(response_prefix, tmp_path)
    f.resume["full_replay_complete"] = False
    return f


def resumed(f, backend):
    storage_ = replay.checkpoint_storage(
        old_replay.state_module,
        f.resume,
        f.destination,
        control=old_replay.CONTROL,
        context_id=old_replay.PROFILE,
        protocol_id="v43-cpu-test",
    )
    function = old_replay.optimized.bind_dependencies(
        old_replay.v32.feedback_gradient, BACKEND_VERSION=old_replay.R3_VERSION, state=storage_
    )
    assert function.__code__ is old_replay.v32.feedback_gradient.__code__
    return old_replay.run(f.fixture, f.destination, backend, function=function)


def test_generic_actual_response_prefix_is_bitwise_original_order(response):
    f, backend = response, old_replay.Backend()
    actual, report = resumed(f, backend)
    assert backend.calls == 186 and report["restored_completed_responses"] == 261
    assert all(torch.equal(actual[n], expected) for n, expected in f.fixture.expected.items())


def test_bad_response_tensor_or_rng_rejected_before_backend(response):
    with (response.source / "state.pt").open("ab") as stream:
        stream.write(b"changed")
    backend = old_replay.Backend()
    with pytest.raises(ValueError, match="bytes changed"):
        resumed(response, backend)
    assert backend.calls == 0


def test_completed_response_prefix_needs_zero_extra_backward(response_prefix, tmp_path):
    source = response_prefix.root / "baseline/response000447"
    record = json.loads((source / "record.json").read_text())
    binding = dict(
        checkpoint_directory=str(source),
        checkpoint=old_replay.entry(source / "record.json"),
        state=dict(path=str(source / "state.pt"), sha256=record["state_sha256"]),
        binding=record["binding"],
        inherited_response_count=447,
        total_response_count=447,
        remaining_response_count=0,
        full_replay_complete=True,
    )
    f = SimpleNamespace(
        fixture=response_prefix, resume=binding, destination=tmp_path / "new/checkpoints"
    )
    backend = old_replay.Backend()
    actual, report = resumed(f, backend)
    assert backend.calls == 0 and report["restored_completed_responses"] == 447
    assert all(torch.equal(actual[n], expected) for n, expected in response_prefix.expected.items())


@pytest.fixture
def cold_episode(tmp_path, monkeypatch):
    worker = importlib.import_module("finqa_v43_worker")
    helper = importlib.import_module("test_finance_v40_worker")
    monkeypatch.setattr(helper, "worker", worker.original)
    f = helper.episode.__wrapped__(tmp_path, monkeypatch)
    control = worker.original.control
    monkeypatch.setattr(worker, "_controller", lambda: control)
    monkeypatch.setattr(control, "__file__", str(f.root / "implementation/finqa_v43_controller.py"))
    scope = dict(allowed_gpu_indices=f.plan["allowed_gpu_indices"], gpu_uuids=f.plan["gpu_uuids"])
    f.plan["gpu_admission_policy"] = worker.policy.policy_record(
        scope=scope, evidence_refs=[{"CPU": True}]
    )
    f.plan["time_policy"] = time_policy.record()
    for name in ("resolve_origin_context", "stage_directory", "require_upstream"):
        monkeypatch.setattr(worker.inheritance, name, getattr(worker.original.inheritance, name))
    monkeypatch.setattr(worker.inheritance, "task_cache_overlay_binding", lambda *a: None)
    monkeypatch.setattr(worker.inheritance, "feedback_resume_binding", lambda *a: None)
    monkeypatch.setattr(worker.inheritance, "replay_resume_binding", lambda *a: None)
    for module in (
        worker,
        worker.admission,
        worker.inheritance,
        worker.policy,
        worker.task_overlay,
        worker.feedback_resume,
        worker.replay_resume,
        worker.time_policy,
    ):
        monkeypatch.setattr(
            module, "__file__", str(f.root / "implementation" / Path(module.__file__).name)
        )
    monkeypatch.setattr(
        worker.original, "__file__", str(f.root / "implementation/finqa_v43_cold_worker.py")
    )
    old_samples = f.bundle.inherited.DeviceSamples
    monkeypatch.setattr(f.bundle.inherited, "DeviceSamples", lambda uuid: old_samples("GPU-fixed"))

    def admit(plan, stage, gpu, directory, deadline, torch_, stop, *, context, **kwargs):
        assert deadline is None and context is f.context and not f.cuda.initialized and not stop()
        f.calls.append(("admission", stage))
        return dict(
            index=4, uuid=plan["gpu_uuids"]["4"], free_mib=24 * 1024, processes=[dict(pid=42)]
        )

    monkeypatch.setattr(worker.admission, "wait_for_pre_cuda_admission", admit)
    f.run = lambda stage: worker.run(f.root, f.directory, stage, 4, None)
    f.worker = worker
    return f


def test_actual_cold_distribution_shell_none_deadline_and_original_resource_gates(cold_episode):
    f = cold_episode
    before = copy.deepcopy(f.context)
    result = f.run("distribution")
    assert result["schema"] == "v43_stage_result.v1" and result["status"] == "COMPLETE"
    assert f.context == before and f.marker.read_bytes() == f.original_bytes
    assert result["resources"]["maximum_allocated_bytes"] == 76 * 1024**3
    assert result["resources"]["minimum_device_free_bytes"] == 2 * 1024**3
    assert result["resources"]["peak_resets_after_model_loading_begins"] == 0
    assert all(
        row["deadline_epoch"] is None
        and row["deadline_pass"] is True
        and row["deadline_limit_enforced"] is False
        for row in result["resources"]["observations"]
    )
    assert f.cuda.resets == 1 and result["model_optimizer_rng_buffers_unchanged"] is True


def test_unlimited_worker_still_rejects_memory_gate_failure(cold_episode):
    f = cold_episode
    f.flags.resource_failure = "model_released.after_cleanup"
    with pytest.raises(ValueError, match="final resource"):
        f.run("distribution")
    assert not (f.directory / "distribution/result/record.json").exists()


def test_null_deadline_stop_still_obeys_user_signal():
    worker = importlib.import_module("finqa_v43_worker")
    request = SimpleNamespace(requested=False, reason=None, signals=lambda: "retained-signals")
    stop = worker.DeadlineStop(request, None)
    assert stop.requested is False and stop.reason is None and stop.signals() == "retained-signals"
    request.requested, request.reason = True, "signal:15"
    assert stop.requested is True and stop.reason == "signal:15"


def test_cache_only_receipt_stage_uses_parent_without_new_task_forward(union):
    f = union
    f.binding["cache_only_receipt_stages"] = ["shard00"]
    f.binding["allowed_new_stages"] = list(tasks.SHARDS)
    cache = f.build("shard00")
    assigned = f.data.plan["assignments"][0]["task_ids"]
    assert all(cache.has(task) for task in assigned)
    assert not cache.commit_allowed
    assert cache.verification_summary()["parent_tasks_strictly_verified"] == 186


def test_cache_only_receipt_stage_cannot_hide_missing_tasks(union):
    union.binding["cache_only_receipt_stages"] = ["shard01"]
    with pytest.raises(ValueError, match="every assigned complete"):
        union.build("shard01")
