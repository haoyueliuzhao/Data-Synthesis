"""CPU-only resource-extension controls, including live Full29's unchanged profile."""

import importlib
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parents[1] / "scripts"))
queue = importlib.import_module("finqa_v21_six_gpu_queue")


def parent():
    return dict(
        id="V20",
        schema="old",
        at="old",
        user_request="old",
        allowed_gpu_indices=[1, 2, 3, 4, 6],
        max_gpu_workers=5,
        cpu_affinity={"1": "node0", "2": "node0", "3": "node0", "4": "node1", "6": "node1"},
        optimized_job_keys=["arm-29-full", "arm-47-full"],
        block_size=8,
        checkpoint_every_responses=16,
        minimum_free_mib=24576,
        validation={"cases": [1, 2, 3, 4], "maximum_optimized_time_ratio": 1.05},
        automatic_numerical_failure_retry=False,
        partial_feedback_resampling=False,
        source_bindings={"replay.py": "unchanged"},
    )


def profile():
    old = parent()
    return dict(
        old,
        id="V21",
        schema="v21_six_gpu_execution_extension.v1",
        allowed_gpu_indices=queue.GPUS,
        max_gpu_workers=6,
        cpu_affinity={**old["cpu_affinity"], "0": "node0"},
        optimized_job_keys=["arm-47-full"],
        resource_extension_source_sha256=queue.own_source(),
        new_CUDA_validation_claimed=False,
        live_Full29_profile_unchanged=True,
        parent_execution_profile={"id": "V20"},
        parent_controller={"id": "parent"},
        inherited_CUDA_validation={"id": "actual-pass"},
        inherited_CUDA_validation_id="actual-pass",
        continued_worker=dict(
            job_key="arm-29-full",
            pid=29,
            birth="birth29",
            gpu=4,
            original_launch={"id": "original-launch"},
            worker_execution_profile={"id": "V20"},
        ),
    )


def bare(tmp_path):
    controller = queue.Supervisor.__new__(queue.Supervisor)
    controller.profile = profile()
    controller.profile_root = tmp_path
    controller.profile_ref = {"id": "V21"}
    controller.continued_parent = {
        "pid": 20,
        "process_start_time_ticks": "parent-birth",
        "script_worktree": str(tmp_path / "old-frozen"),
    }
    controller.history_root = tmp_path / "jobs"
    controller.children = {}
    controller.stop = False
    controller.resume = False
    controller.guard_old_dispatch = lambda: None
    controller.update = lambda *a, **k: None
    controller.reap_profiled = lambda: ([], [])
    return controller


def job(tmp_path, key, **kwargs):
    return dict(
        key=key,
        module="v16_arm_training",
        args=["run-arm"],
        result=tmp_path / key / "result/record.json",
        **kwargs,
    )


def test_resource_extension_retains_numeric_rules():
    queue.check_inheritance(profile(), parent())


@pytest.mark.parametrize(
    "key,value",
    (
        ("block_size", 16),
        ("checkpoint_every_responses", 8),
        ("minimum_free_mib", 1000),
        ("source_bindings", {"replay.py": "changed"}),
        ("validation", {"cases": ["new"], "maximum_optimized_time_ratio": 2}),
        ("automatic_numerical_failure_retry", True),
        ("partial_feedback_resampling", True),
        ("allowed_gpu_indices", [0, 1, 2, 3, 4, 5, 6]),
        ("max_gpu_workers", 7),
        ("optimized_job_keys", ["arm-29-full", "arm-47-full"]),
        ("new_CUDA_validation_claimed", True),
        ("live_Full29_profile_unchanged", False),
    ),
)
def test_unrelated_changes_cannot_hide_in_resource_extension(key, value):
    changed = profile()
    changed[key] = value
    with pytest.raises(ValueError):
        queue.check_inheritance(changed, parent())


def test_inherited_acceptance_keeps_original_id_and_measured_profile(monkeypatch, tmp_path):
    original = dict(id="actual-pass", execution_profile_id="V20", gpu_index=4)
    monkeypatch.setattr(queue.previous, "checked_profile", lambda root: parent())
    monkeypatch.setattr(queue.replay_profile, "admitted_validation", lambda root, plan: original)
    monkeypatch.setattr(queue, "entry", lambda path: {"id": "actual-pass"})
    result = queue.inherited_validation(tmp_path, profile())
    assert result is original
    assert result["execution_profile_id"] == "V20" and result["gpu_index"] == 4


def test_existing_and_new_fulls_have_distinct_restore_profiles(tmp_path):
    controller = bare(tmp_path)
    jobs = {j["key"]: j for j in controller.arm_jobs(tmp_path / "launcher")}
    assert len(jobs) == 15
    assert jobs["arm-29-full"]["script"].name == "finqa_v20_five_gpu_queue.py"
    assert jobs["arm-29-full"]["args"][-1] == queue.PARENT
    assert jobs["arm-47-full"]["script"].name == "finqa_v21_six_gpu_queue.py"
    assert jobs["arm-47-full"]["args"][-1] == tmp_path
    assert controller.worker_profile("arm-29-full") == {"id": "V20"}
    assert controller.worker_profile("arm-47-full") == {"id": "V21"}
    assert (
        controller.run_remaining_mainline.__func__
        is queue.recovery.Supervisor.run_remaining_mainline
    )


@pytest.mark.parametrize("key,expected", (("arm-29-full", "V20"), ("arm-47-full", "V21")))
def test_completion_cannot_rebind_live_workers(monkeypatch, tmp_path, key, expected):
    controller = bare(tmp_path)
    monkeypatch.setattr(queue, "marker_complete", lambda path: True)
    result = dict(
        execution_profile={"id": expected},
        execution_producer="v19_profiled_worker.v1",
        validation_id="actual-pass",
    )
    monkeypatch.setattr(queue, "checked", lambda path: result)
    assert controller.job_complete(job(tmp_path, key))
    result["execution_profile"] = {"id": "V21" if expected == "V20" else "V20"}
    with pytest.raises(ValueError):
        controller.job_complete(job(tmp_path, key))


def test_live_Full29_uses_its_actual_parent_for_exit_receipts(monkeypatch, tmp_path):
    controller = bare(tmp_path)
    child = controller.profile["continued_worker"]
    child["attempt"] = str(tmp_path / "original-attempt")
    controller.job_complete = lambda j: False
    rest = []
    monkeypatch.setattr(
        queue.original_queue.Supervisor,
        "recover_active",
        lambda self, jobs: rest.extend(j["key"] for j in jobs),
    )
    controller.recover_active([job(tmp_path, "arm-29-full"), job(tmp_path, "arm-47-full")])
    process = controller.children["arm-29-full"]["process"]
    assert process.parent == controller.continued_parent
    assert process.child["attempt"] == child["attempt"]
    assert rest == ["arm-47-full"]
    monkeypatch.setattr(
        queue.recovery, "identity", lambda pid: "parent-birth" if pid == 20 else None
    )
    assert process.poll() is None  # It waits for the real parent's durable exit, not a guess.
    directory = Path(child["attempt"]) / "exit"
    queue.persist(directory, queue.bound(dict(pid=29, key="arm-29-full", exit_code=3)))
    assert process.poll() == 3


def test_five_live_workers_admit_only_Full47_on_GPU0(monkeypatch, tmp_path):
    controller = bare(tmp_path)
    controller.children = {str(g): dict(gpu=g, protected=True) for g in (1, 2, 3, 4, 6)}
    controller.recover_active = lambda jobs: None
    controller.job_complete = lambda j: j["module"] == "validation_gate"
    monkeypatch.setattr(queue, "inherited_validation", lambda *a: {"id": "actual-pass"})
    monkeypatch.setattr(
        queue.previous, "gpu_inventory", lambda: [dict(index=g, free=80000) for g in range(8)]
    )
    launched = []

    def launch(task, *, gpu):
        launched.append((task["key"], gpu))
        controller.children[task["key"]] = dict(gpu=gpu, protected=False)

    def stop(_seconds):
        controller.children.clear()
        controller.stop = True

    controller.launch = launch
    monkeypatch.setattr(queue.previous.time, "sleep", stop)
    assert (
        controller.gpu_queue(
            [
                job(tmp_path, "arm-47-full", requires_validation=True),
                job(tmp_path, "arm-11-static"),
            ],
            queue.GPUS,
        )
        is False
    )
    assert launched == [("arm-47-full", 0)]
    assert queue.previous.GPUS == [1, 2, 3, 4, 6]  # No mutation of the running parent's module.


@pytest.mark.parametrize("gpu,count", ((5, 5), (7, 5), (0, 6)))
def test_other_cards_and_seventh_worker_are_rejected(tmp_path, gpu, count):
    controller = bare(tmp_path)
    controller.children = {str(i): {} for i in range(count)}
    with pytest.raises(ValueError, match="six-GPU concurrency"):
        controller.launch(job(tmp_path, "arm-47-full"), gpu=gpu)


def test_live_Full29_is_never_relaunched(tmp_path):
    controller = bare(tmp_path)
    with pytest.raises(ValueError, match="never relaunch"):
        controller.launch(job(tmp_path, "arm-29-full"), gpu=0)


@pytest.mark.parametrize("extra_launch,parent_state", ((False, "S"), (True, "S"), (False, "T")))
def test_draining_parent_must_not_dispatch_or_be_paused(monkeypatch, extra_launch, parent_state):
    value = {"parent_drain_receipt": "drain", "parent_controller": "controller"}
    records = {
        "drain": {"parent_launch_bindings": [{"id": "old"}]},
        "controller": {"pid": 20, "process_start_time_ticks": "birth"},
    }
    monkeypatch.setattr(queue, "read_ref", lambda ref: records[ref])
    monkeypatch.setattr(
        queue,
        "parent_launches",
        lambda: [{"id": "old"}] + ([{"id": "new"}] if extra_launch else []),
    )
    monkeypatch.setattr(queue, "identity", lambda pid: "birth")
    monkeypatch.setattr(queue.replay_profile, "process_state", lambda pid: parent_state)
    if extra_launch or parent_state == "T":
        with pytest.raises(ValueError):
            queue.guard_parent(value)
    else:
        queue.guard_parent(value)
