"""CPU-only controls for the GPU4 resource extension, with no actual child or GPU."""

import copy
import importlib
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parents[1] / "scripts"))
queue = importlib.import_module("finqa_v20_five_gpu_queue")


def parent_profile():
    return dict(
        id="old",
        schema="old",
        at="original",
        user_request="old",
        allowed_gpu_indices=[1, 2, 3, 6],
        max_gpu_workers=4,
        cpu_affinity={"1": "node0", "2": "node0", "3": "node0", "6": "node1"},
        paused_dispatcher={"id": "previous-pause"},
        block_size=8,
        checkpoint_every_responses=16,
        minimum_free_mib=24576,
        partial_feedback_resampling=False,
        automatic_numerical_failure_retry=False,
        validation={"cases": ["fixed1", "fixed2", "fixed3", "fixed4"], "ratio": 1.05},
        original_runtime_binding={"numeric.py": "fixed"},
    )


def extension(parent):
    return dict(
        parent,
        id="new",
        schema="v20_five_gpu_execution_extension.v1",
        allowed_gpu_indices=queue.GPUS,
        max_gpu_workers=5,
        cpu_affinity={**parent["cpu_affinity"], "4": "node1"},
        resource_extension_source_sha256=queue.own_source(),
        restart_or_migrate_live_workers=False,
        GPU4_exclusive_ownership_claimed=False,
    )


def bare(tmp_path):
    controller = queue.Supervisor.__new__(queue.Supervisor)
    controller.profile_root = tmp_path
    controller.profile = {"id": "profile", "minimum_free_mib": 24576}
    controller.children = {}
    controller.stop = False
    controller.recover_active = lambda jobs: None
    controller.guard_old_dispatch = lambda: None
    controller.update = lambda *args, **kw: None
    controller.reap_profiled = lambda: ([], [])
    controller.job_complete = lambda j: False
    return controller


def task(tmp_path, key, **kwargs):
    return dict(
        key=key,
        module="v16_arm_training",
        args=["run-arm"],
        result=tmp_path / key / "result/record.json",
        **kwargs,
    )


def test_extension_changes_only_devices_and_capacity():
    parent = parent_profile()
    queue.check_inheritance(extension(parent), parent)


@pytest.mark.parametrize(
    "key,value",
    (
        ("block_size", 16),
        ("checkpoint_every_responses", 8),
        ("minimum_free_mib", 8192),
        ("partial_feedback_resampling", True),
        ("automatic_numerical_failure_retry", True),
        ("validation", {"cases": ["replacement"], "ratio": 1.5}),
        ("original_runtime_binding", {"numeric.py": "changed"}),
        ("allowed_gpu_indices", [0, 1, 2, 3, 4, 6]),
        ("max_gpu_workers", 6),
    ),
)
def test_resource_extension_rejects_unrelated_changes(key, value):
    parent = parent_profile()
    changed = extension(parent)
    changed[key] = value
    with pytest.raises(ValueError):
        queue.check_inheritance(changed, parent)


def test_only_pending_fulls_and_gate_route_to_resource_wrapper(tmp_path):
    controller = bare(tmp_path)
    jobs = controller.arm_jobs(tmp_path / "launcher")
    assert len(jobs) == 15
    changed = [j for j in jobs if j.get("script")]
    assert [j["key"] for j in changed] == ["arm-29-full", "arm-47-full"]
    assert all(j["script"].name == "finqa_v20_five_gpu_queue.py" for j in changed)
    assert all(j["requires_validation"] for j in changed)
    assert controller.validation_job()["args"] == ["validate", "--root", tmp_path]
    assert (
        controller.run_remaining_mainline.__func__
        is queue.recovery.Supervisor.run_remaining_mainline
    )
    assert queue.Supervisor.recover_active is queue.base_queue.Supervisor.recover_active


def test_four_protected_workers_allow_only_the_gate_on_GPU4(monkeypatch, tmp_path):
    controller = bare(tmp_path)
    controller.children = {str(g): dict(gpu=g, protected=True) for g in (1, 2, 3, 6)}
    controller.eligible_job = lambda j: not j.get("requires_validation")
    launched = []

    def launch(job, *, gpu):
        launched.append((job["key"], gpu))
        controller.children[job["key"]] = dict(gpu=gpu, protected=False)

    controller.launch = launch
    monkeypatch.setattr(
        queue, "gpu_inventory", lambda: [dict(index=g, free=48000) for g in range(8)]
    )
    monkeypatch.setattr(queue.os, "kill", lambda *a: pytest.fail("never signal a Student"))

    def stop(_seconds):
        controller.children.clear()
        controller.stop = True

    monkeypatch.setattr(queue.time, "sleep", stop)
    assert (
        controller.gpu_queue(
            [
                task(tmp_path, "arm-29-full", requires_validation=True),
                task(tmp_path, "arm-11-static"),
            ],
            queue.GPUS,
        )
        is False
    )
    assert launched == [("replay-CUDA-equivalence-gate", 4)]


def test_GPU4_stays_queued_if_it_has_insufficient_headroom(monkeypatch, tmp_path):
    controller = bare(tmp_path)
    controller.children = {str(g): dict(gpu=g, protected=True) for g in (1, 2, 3, 6)}
    controller.eligible_job = lambda job: True
    controller.launch = lambda *a, **kw: pytest.fail("headroom must not be relaxed")
    monkeypatch.setattr(
        queue, "gpu_inventory", lambda: [dict(index=g, free=20000) for g in range(8)]
    )

    def stop(_seconds):
        controller.children.clear()
        controller.stop = True

    monkeypatch.setattr(queue.time, "sleep", stop)
    assert controller.gpu_queue([task(tmp_path, "static")], queue.GPUS) is False


@pytest.mark.parametrize("gpu,count", ((0, 4), (5, 4), (7, 4), (4, 5)))
def test_launch_rejects_other_cards_and_sixth_worker(tmp_path, gpu, count):
    controller = bare(tmp_path)
    controller.children = {str(i): {} for i in range(count)}
    with pytest.raises(ValueError, match="five-GPU concurrency"):
        controller.launch(task(tmp_path, "anything"), gpu=gpu)


def test_worker_and_validation_reuse_bytecode_without_patching_frozen_globals(
    monkeypatch, tmp_path
):
    old_worker_loader = queue.base_worker.run.__globals__["checked_profile"]
    old_validator_loader = queue.base_validation.run.__globals__["checked_profile"]
    calls = []

    def bind(function, **bindings):
        assert bindings == {"checked_profile": queue.checked_profile}
        calls.append(function)
        return lambda *args, **kwargs: dict(args=args, kwargs=copy.copy(kwargs))

    monkeypatch.setattr(queue, "bind_dependencies", bind)
    assert queue.validate(tmp_path, gpu_index=4)["kwargs"]["gpu_index"] == 4
    result = queue.run_arm(tmp_path, 29, "Full", 4, profile_root=tmp_path, resume=True)
    assert result["args"] == (tmp_path, 29, "Full", 4)
    assert result["kwargs"] == dict(profile_root=tmp_path, resume=True)
    assert calls == [queue.base_validation.run, queue.base_worker.run]
    assert queue.base_worker.run.__globals__["checked_profile"] is old_worker_loader
    assert queue.base_validation.run.__globals__["checked_profile"] is old_validator_loader
