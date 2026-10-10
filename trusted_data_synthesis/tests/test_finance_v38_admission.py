"""CPU-only admission races and unchanged hard boundaries."""

import hashlib
import importlib
import json
import os
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest

sys.path.insert(0, str(Path(__file__).parents[1] / "scripts"))
subject = importlib.import_module("finqa_v38_admission")


@pytest.fixture
def admission(tmp_path):
    class Clock:
        now = 1000.0

        def __call__(self):
            return self.now

        def sleep(self, seconds):
            self.now += seconds

    clock = Clock()
    ready = dict(index=4, uuid="GPU-four", free_mib=80 * 1024, processes=[])
    state = SimpleNamespace(
        clock=clock,
        rows=[ready],
        ready=ready,
        initialized=False,
        stopped=False,
        rss=8 * subject.GIB,
        peak_rss=8 * subject.GIB,
        available=256 * subject.GIB,
        process_missing=False,
        checks=0,
    )

    def initialized():
        state.checks += 1
        return state.initialized

    def process(_pid):
        return (
            None
            if state.process_missing
            else dict(rss_bytes=state.rss, peak_rss_bytes=state.peak_rss)
        )

    state.kwargs = dict(
        plan=dict(id="protocol", gpu_uuids={"4": "GPU-four"}),
        stage="distribution",
        gpu_index=4,
        directory=tmp_path / "distribution",
        deadline_epoch=1010.0,
        torch=SimpleNamespace(cuda=SimpleNamespace(is_initialized=initialized)),
        stop_requested=lambda: state.stopped,
        context_id="same-point-context",
        inventory=lambda: state.rows,
        host_memory=lambda: dict(available_bytes=state.available),
        process_memory=process,
        birth=lambda _pid: "original-birth",
        clock=clock,
        sleep=clock.sleep,
        poll_seconds=2.0,
    )
    state.status = lambda: json.loads(
        (state.kwargs["directory"] / "pre_cuda_wait/status.json").read_text()
    )
    return state


def test_already_idle_returns_real_row_and_bound_ready_heartbeat(admission):
    a = admission
    assert subject.wait_for_pre_cuda_admission(**a.kwargs) is a.ready
    heartbeat = a.status()
    assert heartbeat["phase"] == "READY" and heartbeat["waiting_seconds"] == 0
    assert heartbeat["protocol_id"] == "protocol"
    assert heartbeat["context_id"] == "same-point-context"
    assert heartbeat["pid"] == os.getpid() and heartbeat["birth"] == "original-birth"
    assert heartbeat["gpu_uuid"] == "GPU-four" and heartbeat["cuda_initialized"] is False


def test_arriving_external_process_waits_in_same_worker_then_admits(admission):
    a = admission
    busy = dict(a.ready, processes=[dict(pid=42, used_memory_mib="25000")], free_mib=54000)
    a.rows = [busy]
    seen = []

    def sleep(seconds):
        seen.append(a.status())
        a.clock.sleep(seconds)
        a.rows = [a.ready]

    a.kwargs["sleep"] = sleep
    assert subject.wait_for_pre_cuda_admission(**a.kwargs) is a.ready
    assert seen[0]["phase"] == "WAITING"
    assert seen[0]["reason"] == "external_gpu_process"
    assert a.status()["waiting_seconds"] == 2 and a.checks == 4
    assert a.status()["waiting_started_epoch"] == 1000
    assert a.status()["waiting_finished_epoch"] == 1002
    assert a.status()["waiting_started_monotonic"] == 1000
    assert a.status()["waiting_finished_monotonic"] == 1002
    records = sorted((a.kwargs["directory"] / "pre_cuda_wait").glob("event*/record.json"))
    assert [json.loads(p.read_text())["phase"] for p in records] == ["WAITING", "READY"]
    assert seen[0]["pid"] == a.status()["pid"] == os.getpid()


def test_low_free_memory_alone_waits_without_extending_deadline(admission):
    a = admission
    a.rows = [dict(a.ready, free_mib=subject.MINIMUM_FREE_MIB - 1)]
    a.kwargs["deadline_epoch"] = 1003.0
    with pytest.raises(subject.AdmissionDeadlineExceeded):
        subject.wait_for_pre_cuda_admission(**a.kwargs)
    assert a.clock.now == 1003.0
    assert a.status()["phase"] == "TIMED_OUT" and a.status()["waiting_seconds"] == 3.0
    assert a.status()["deadline_epoch"] == 1003.0


@pytest.mark.parametrize("mutation,match", [("missing", "missing"), ("uuid", "UUID changed")])
def test_device_identity_is_a_hard_failure_not_a_wait(admission, mutation, match):
    a = admission
    a.rows = [] if mutation == "missing" else [dict(a.ready, uuid="GPU-another")]
    with pytest.raises(subject.AdmissionError, match=match):
        subject.wait_for_pre_cuda_admission(**a.kwargs)
    assert a.clock.now == 1000 and a.status()["phase"] == "FAILED"


@pytest.mark.parametrize("field", ["rss", "peak_rss", "available", "process_missing"])
def test_host_and_rss_unknown_or_failed_gates_never_wait(admission, field):
    a = admission
    setattr(
        a,
        field,
        True if field == "process_missing" else 0 if field == "available" else 193 * subject.GIB,
    )
    with pytest.raises(subject.AdmissionError):
        subject.wait_for_pre_cuda_admission(**a.kwargs)
    assert a.clock.now == 1000 and a.status()["phase"] == "FAILED"


def test_shard_uses_160_gib_instead_of_coordinator_192(admission):
    a = admission
    a.kwargs["stage"] = "shard00"
    a.rss = a.peak_rss = 161 * subject.GIB
    with pytest.raises(subject.AdmissionError, match="RSS"):
        subject.wait_for_pre_cuda_admission(**a.kwargs)


def test_cuda_is_rechecked_after_every_sleep(admission):
    a = admission
    a.rows = [dict(a.ready, processes=[dict(pid=42)])]

    def sleep(seconds):
        a.clock.sleep(seconds)
        a.initialized = True
        a.rows = [a.ready]

    a.kwargs["sleep"] = sleep
    with pytest.raises(subject.AdmissionError, match="CUDA initialized"):
        subject.wait_for_pre_cuda_admission(**a.kwargs)
    assert a.checks == 3 and a.status()["cuda_initialized"] is True


def test_own_cuda_process_is_not_treated_as_external_wait(admission):
    a = admission
    a.rows = [dict(a.ready, processes=[dict(pid=os.getpid())])]
    with pytest.raises(subject.AdmissionError, match="unexpectedly owns"):
        subject.wait_for_pre_cuda_admission(**a.kwargs)


def test_signal_during_wait_stops_before_idle_cuda_admission(admission):
    a = admission
    a.rows = [dict(a.ready, processes=[dict(pid=42)])]

    def sleep(seconds):
        a.clock.sleep(seconds)
        a.stopped = True
        a.rows = [a.ready]

    a.kwargs["sleep"] = sleep
    with pytest.raises(subject.AdmissionStopped):
        subject.wait_for_pre_cuda_admission(**a.kwargs)
    assert a.status()["phase"] == "STOPPED"


def test_a_second_call_cannot_rewrite_the_existing_admission(admission):
    a = admission
    subject.wait_for_pre_cuda_admission(**a.kwargs)
    original = a.status()
    with pytest.raises(subject.AdmissionError, match="already exists"):
        subject.wait_for_pre_cuda_admission(**a.kwargs)
    assert a.status() == original


@pytest.mark.parametrize(
    "change,error,phase",
    [
        ("deadline", subject.AdmissionDeadlineExceeded, "TIMED_OUT"),
        ("stop", subject.AdmissionStopped, "STOPPED"),
        ("cuda", subject.AdmissionError, "FAILED"),
    ],
)
def test_slow_or_interrupted_cpu_observation_cannot_publish_ready(admission, change, error, phase):
    a = admission

    def observation():
        if change == "deadline":
            a.clock.now = a.kwargs["deadline_epoch"]
        elif change == "stop":
            a.stopped = True
        else:
            a.initialized = True
        return [a.ready]

    a.kwargs["inventory"] = observation
    with pytest.raises(error):
        subject.wait_for_pre_cuda_admission(**a.kwargs)
    assert a.status()["phase"] == phase
    records = (a.kwargs["directory"] / "pre_cuda_wait").glob("event*/record.json")
    assert all(json.loads(record.read_text())["phase"] != "READY" for record in records)


def test_unicode_process_name_uses_controller_canonical_utf8_hash(admission):
    a = admission
    process_name = "/项目/外部任务/模型🧪"
    a.rows = [dict(a.ready, processes=[dict(pid=42, process_name=process_name)])]

    def check_record(record):
        body = {key: value for key, value in record.items() if key != "id"}
        canonical = json.dumps(
            body, ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False
        ).encode()
        assert hashlib.sha256(canonical).hexdigest() == record["id"]
        assert record["gpu"]["processes"][0]["process_name"] == process_name

    def sleep(seconds):
        check_record(a.status())
        a.clock.sleep(seconds)
        a.rows = [a.ready]

    a.kwargs["sleep"] = sleep
    subject.wait_for_pre_cuda_admission(**a.kwargs)
    event = a.kwargs["directory"] / "pre_cuda_wait/event000000/record.json"
    check_record(json.loads(event.read_text()))
    assert process_name in event.read_text()
