"""Focused CPU process-lifecycle tests; no model, CUDA or API calls."""

import hashlib
import importlib
import json
import subprocess
import sys
import time
from pathlib import Path
from types import SimpleNamespace

import pytest

sys.path.insert(0, str(Path(__file__).parents[1] / "scripts"))
lifecycle = importlib.import_module("finqa_v36_lifecycle")
GIB = 1024**3


def digest(value):
    return hashlib.sha256(
        json.dumps(value, sort_keys=True, separators=(",", ":")).encode()
    ).hexdigest()


def publish(path, body):
    path.parent.mkdir(parents=True, exist_ok=True)
    result = {**body, "id": digest(body)}
    path.write_text(json.dumps(result) + "\n")
    return result


def original_validator(protocol, stage, result, _plan):
    lifecycle.require(
        result["protocol_id"] == protocol["id"]
        and result["stage"] == stage
        and result["status"] == "COMPLETE"
        and result["original_gates_passed"] is True,
        "original numerical/resource validation failed",
    )
    return result


def result(stage):
    return dict(
        protocol_id="protocol",
        stage=stage,
        status="COMPLETE",
        model_released=True,
        original_gates_passed=True,
        resources=dict(
            observations=[
                dict(
                    label="model_released.after_cleanup",
                    boundary=True,
                    passed=True,
                    allocated_pass=True,
                    free_pass=True,
                )
            ]
        ),
    )


class Lock:
    closed = False

    def close(self):
        self.closed = True


class Process:
    def __init__(self, pid):
        self.pid, self.code = pid, None

    def poll(self):
        return self.code

    def wait(self, *args, **kwargs):
        pytest.fail("lifecycle polling must never synchronously wait on a live child")


class Base:
    def __init__(self, root):
        self.root = root
        self.protocol = dict(id="protocol")
        self.task_plan = {}
        self.active, self.results = {}, {}
        self.exits = []
        self.updates = []
        self.deadline = time.monotonic() + 10_000
        self.lifecycle_api = SimpleNamespace(
            digest=digest,
            publish=publish,
            check_result=original_validator,
            now=lambda: "test-time",
            POLL_SECONDS=0.02,
            TERM_GRACE_SECONDS=600,
            MINIMUM_DEVICE_FREE_BYTES=2 * GIB,
            HOST_RAM=dict(
                shard_rss_limit_bytes=160 * GIB,
                coordinator_rss_limit_bytes=192 * GIB,
                reserve_bytes=96 * GIB,
            ),
            host_memory=lambda: dict(available_bytes=800 * GIB),
            inventory=lambda: [
                dict(index=i, uuid=f"GPU-{i}", free_mib=80 * 1024, processes=[]) for i in (4, 5, 7)
            ],
            STAGE_GPU=dict(shard01=4, shard02=5, coordinator=7),
        )

    def update(self, phase, **_):
        self.updates.append(phase)

    def time_gate(self):
        lifecycle.require(lifecycle.time.monotonic() < self.deadline, "global deadline expired")

    def record_exit(self, stage, *, stopped=False):
        item = self.active[stage]
        assert item["process"].poll() is not None
        self.exits.append((stage, item["process"].poll(), stopped))
        item["lock"].close()
        del self.active[stage]


class Controller(lifecycle.LifecycleMixin, Base):
    pass


def add_worker(controller, stage="shard01", process=None, *, worker="worker.py", birth=None):
    process = process or Process(1000 + len(controller.active))
    index = controller.lifecycle_api.STAGE_GPU[stage]
    item = dict(
        process=process,
        lock=Lock(),
        launch=dict(
            pid=process.pid,
            birth=birth or f"birth-{process.pid}",
            worker=worker,
            stage=stage,
            gpu_index=index,
            gpu_uuid=f"GPU-{index}",
        ),
    )
    controller.active[stage] = item
    return item


def proc(item, *, missing=False):
    return dict(
        pid=item["launch"]["pid"],
        state=None if missing else "R",
        flags=None if missing else 0,
        birth_observations=[] if missing else [item["launch"]["birth"]],
        command=None
        if missing
        else ["python", item["launch"]["worker"], "--stage", item["launch"]["stage"]],
        rss_bytes=None if missing else GIB,
        peak_rss_bytes=None if missing else 2 * GIB,
        read_errors={"stat": {"type": "FileNotFoundError", "errno": 2}} if missing else {},
    )


def write_result(controller, stage="shard01", **changes):
    return publish(controller.root / stage / "result/record.json", {**result(stage), **changes})


def test_real_cpu_child_commits_then_drains_longer_than_two_seconds(tmp_path):
    controller = Controller(tmp_path)
    destination = tmp_path / "shard01/result/record.json"
    destination.parent.mkdir(parents=True)
    body = result("shard01")
    payload = json.dumps({**body, "id": digest(body)}) + "\n"
    code = (
        "import pathlib,sys,time; "
        "pathlib.Path(sys.argv[1]).write_text(sys.argv[2]); time.sleep(3.0)"
    )
    child = subprocess.Popen(
        [sys.executable, "-c", code, str(destination), payload, "--stage", "shard01"],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.PIPE,
    )
    try:
        snapshot = lifecycle.read_proc_snapshot(child.pid)
        item = add_worker(
            controller, process=child, worker="-c", birth=snapshot["birth_observations"][-1]
        )
        deadline = time.monotonic() + 5
        while not destination.exists():
            assert time.monotonic() < deadline
            time.sleep(0.01)
        controller.collect_finished()
        assert item["lifecycle_state"] == lifecycle.DRAINING and not item["lock"].closed
        time.sleep(2.1)
        assert child.poll() is None
        controller.observe_host()
        controller.collect_finished()
        assert "shard01" in controller.active and "shard01" not in controller.results
        while child.poll() is None:
            assert time.monotonic() < deadline
            controller.observe_host()
            controller.collect_finished()
            time.sleep(0.02)
        controller.collect_finished()
        assert item["lifecycle_state"] == lifecycle.SUCCEEDED and item["lock"].closed
        assert controller.exits == [("shard01", 0, False)]
    finally:
        if child.poll() is None:
            child.terminate()
        child.wait(timeout=5)


@pytest.mark.parametrize("code,has_result", [(1, True), (0, False)])
def test_abnormal_exit_or_no_result_never_becomes_success(tmp_path, code, has_result):
    controller = Controller(tmp_path)
    item = add_worker(controller)
    if has_result:
        write_result(controller)
    item["process"].code = code
    with pytest.raises(ValueError, match="unsuccessfully|without a committed result"):
        controller.collect_finished()
    assert "shard01" not in controller.results and item["lock"].closed


@pytest.mark.parametrize("changes", [dict(original_gates_passed=False), dict(model_released=False)])
def test_complete_word_cannot_bypass_original_validation_or_model_release(tmp_path, changes):
    controller = Controller(tmp_path)
    item = add_worker(controller)
    write_result(controller, **changes)
    with pytest.raises(ValueError):
        controller.collect_finished()
    assert item["lifecycle_state"] == lifecycle.RUNNING and not item["lock"].closed


def test_missing_rss_only_allowed_after_trusted_complete_and_never_filled_with_zero(tmp_path):
    controller = Controller(tmp_path)
    item = add_worker(controller)
    controller.lifecycle_proc_reader = lambda _: proc(item, missing=True)
    with pytest.raises(ValueError, match="uncommitted worker identity unavailable"):
        controller.observe_host()
    write_result(controller)
    controller.collect_finished()
    controller.observe_host()
    records = [
        json.loads(path.read_text())
        for path in sorted((tmp_path / "lifecycle").glob("*/record.json"))
    ]
    snapshot = [row for row in records if row["kind"] == "host_gpu_process_observation"][-1]
    assert snapshot["workers"][0]["proc"]["rss_bytes"] is None
    assert snapshot["workers"][0]["observation_gaps"] == ["birth", "command", "RSS"]
    assert item["lock"].closed is False and "shard01" in controller.active


def test_incomplete_result_json_remains_running_with_strict_resource_observation(tmp_path):
    controller = Controller(tmp_path)
    item = add_worker(controller)
    path = tmp_path / "shard01/result/record.json"
    path.parent.mkdir(parents=True)
    path.write_text('{"status":')
    controller.collect_finished()
    assert item["lifecycle_state"] == lifecycle.RUNNING
    controller.lifecycle_proc_reader = lambda _: proc(item, missing=True)
    with pytest.raises(ValueError, match="uncommitted"):
        controller.observe_host()


@pytest.mark.parametrize(
    "conflict", ["birth", "command", "rss", "partial_rss", "partial_peak", "gpu_free", "host_free"]
)
def test_real_identity_or_resource_failures_are_not_draining_exemptions(tmp_path, conflict):
    controller = Controller(tmp_path)
    item = add_worker(controller)
    write_result(controller)
    controller.collect_finished()
    snapshot = proc(item)
    if conflict == "birth":
        snapshot["birth_observations"] = ["foreign-birth"]
    elif conflict == "command":
        snapshot["command"] = ["python", "foreign.py", "--stage", "shard01"]
    elif conflict == "rss":
        snapshot["peak_rss_bytes"] = 161 * GIB
    elif conflict == "partial_rss":
        snapshot.update(rss_bytes=None, peak_rss_bytes=161 * GIB)
    elif conflict == "partial_peak":
        snapshot.update(rss_bytes=161 * GIB, peak_rss_bytes=None)
    elif conflict == "gpu_free":
        controller.lifecycle_api.inventory = lambda: [
            dict(index=4, uuid="GPU-4", free_mib=1024, processes=[])
        ]
    else:
        controller.lifecycle_api.host_memory = lambda: dict(available_bytes=95 * GIB)
    controller.lifecycle_proc_reader = lambda _: snapshot
    with pytest.raises(ValueError):
        controller.observe_host()
    assert not item["lock"].closed


def test_one_drainer_does_not_block_other_workers_observation_or_success(tmp_path):
    controller = Controller(tmp_path)
    first = add_worker(controller, "shard01")
    second = add_worker(controller, "shard02")
    write_result(controller, "shard01")
    controller.collect_finished()
    episode = dict(controller._lifecycle_episode)
    controller.lifecycle_proc_reader = lambda pid: (
        proc(first, missing=True) if pid == first["launch"]["pid"] else proc(second)
    )
    controller.observe_host()
    write_result(controller, "shard02")
    second["process"].code = 0
    controller.collect_finished()
    assert second["lock"].closed and "shard02" in controller.results
    assert not first["lock"].closed and "shard01" in controller.active
    assert controller._lifecycle_episode == episode


def test_result_committing_between_first_result_read_and_proc_gap_is_rechecked(tmp_path):
    controller = Controller(tmp_path)
    item = add_worker(controller)

    def publish_while_proc_is_read(_pid):
        write_result(controller)
        return proc(item, missing=True)

    controller.lifecycle_proc_reader = publish_while_proc_is_read
    controller.observe_host()
    assert item["lifecycle_state"] == lifecycle.DRAINING
    assert not item["lock"].closed and "shard01" not in controller.results


def test_draining_episode_deadline_is_shared_fixed_and_new_dispatch_forbidden(
    tmp_path, monkeypatch
):
    current = [1000.0]
    monkeypatch.setattr(
        lifecycle, "time", SimpleNamespace(monotonic=lambda: current[0], time=lambda: current[0])
    )
    controller = Controller(tmp_path)
    first = add_worker(controller, "shard01")
    second = add_worker(controller, "shard02")
    write_result(controller, "shard01")
    controller.collect_finished()
    current[0] = 1100
    write_result(controller, "shard02")
    controller.collect_finished()
    assert first["lifecycle_draining_deadline"] == second["lifecycle_draining_deadline"] == 1600
    with pytest.raises(ValueError, match="draining grace cannot dispatch"):
        controller._lifecycle_launch_gate()
    current[0] = 1600
    with pytest.raises(ValueError, match="exceeded 600"):
        controller.collect_finished()


def test_finished_episode_closes_even_if_another_worker_is_still_running(tmp_path, monkeypatch):
    current = [1000.0]
    monkeypatch.setattr(
        lifecycle, "time", SimpleNamespace(monotonic=lambda: current[0], time=lambda: current[0])
    )
    controller = Controller(tmp_path)
    first = add_worker(controller, "shard01")
    second = add_worker(controller, "shard02")
    write_result(controller, "shard01")
    controller.collect_finished()
    first["process"].code = 0
    controller.collect_finished()
    assert controller._lifecycle_episode is None
    current[0] = 1800
    write_result(controller, "shard02")
    controller.collect_finished()
    assert second["lifecycle_draining_deadline"] == 2400


def test_committed_result_changed_during_drain_fails_final_validation(tmp_path):
    controller = Controller(tmp_path)
    item = add_worker(controller)
    write_result(controller)
    controller.collect_finished()
    write_result(controller, extra="unexpected rewritten result")
    item["process"].code = 0
    with pytest.raises(ValueError, match="changed while draining"):
        controller.collect_finished()
    assert item["lock"].closed and "shard01" not in controller.results
