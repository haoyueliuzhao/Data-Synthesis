"""CPU-only shared-device races; original stop, identity, RAM and deadline gates."""

import importlib
import json
import os
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest

sys.path.insert(0, str(Path(__file__).parents[1] / "scripts"))
subject = importlib.import_module("finqa_v41_admission")


@pytest.fixture
def admission(tmp_path):
    class Clock:
        now = 1000.0

        def __call__(self):
            return self.now

        def sleep(self, seconds):
            self.now += seconds

    clock = Clock()
    scope = dict(allowed_gpu_indices=list(subject.ALLOWED_GPUS), gpu_uuids=dict(subject.GPU_UUIDS))
    plan = dict(
        id="V41_CPU_ONLY",
        **scope,
        gpu_admission_policy=subject.policy.policy_record(
            scope=scope, evidence_refs=[{"mock": True}]
        ),
    )
    ready = dict(
        index=4,
        uuid=subject.GPU_UUIDS["4"],
        free_mib=32 * 1024,
        processes=[dict(pid=42, used_memory_mib="12000")],
    )
    state = SimpleNamespace(
        clock=clock,
        ready=ready,
        rows=[ready],
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

    state.kwargs = dict(
        plan=plan,
        stage="virtual_point",
        context_id="original-context",
        context={"id": "original-context", "feedback": {"mode": "first_sampling"}},
        gpu_index=4,
        directory=tmp_path / "virtual_point",
        deadline_epoch=1010.0,
        torch=SimpleNamespace(cuda=SimpleNamespace(is_initialized=initialized)),
        stop_requested=lambda: state.stopped,
        inventory=lambda: state.rows,
        host_memory=lambda: dict(available_bytes=state.available),
        process_memory=lambda _pid: (
            None
            if state.process_missing
            else dict(rss_bytes=state.rss, peak_rss_bytes=state.peak_rss)
        ),
        birth=lambda _pid: "same-birth",
        clock=clock,
        sleep=clock.sleep,
        poll_seconds=2,
    )
    state.status = lambda: json.loads(
        (state.kwargs["directory"] / "pre_cuda_wait/status.json").read_text()
    )
    return state


def test_shared_gpu_is_accepted_and_real_process_inventory_is_not_fabricated(admission):
    a = admission
    assert subject.wait_for_pre_cuda_admission(**a.kwargs) is a.ready
    heartbeat = a.status()
    assert heartbeat["schema"] == "v39_pre_cuda_admission.v1"
    assert heartbeat["phase"] == "READY"
    assert heartbeat["memory_phase"] == "virtual_first_sampling"
    assert heartbeat["minimum_free_mib"] == 32 * 1024
    assert heartbeat["gpu"]["processes"] == [{"pid": 42, "used_memory_mib": "12000"}]
    assert heartbeat["gpu_admission_policy_schema"] == subject.POLICY_SCHEMA
    assert heartbeat["pid"] == os.getpid() and heartbeat["birth"] == "same-birth"
    assert heartbeat["waiting_seconds"] == 0


def test_dispatch_sufficient_then_cpu_preparation_race_waits_in_same_worker(admission):
    a = admission
    assert subject.policy.eligible_gpu(
        a.ready, a.kwargs["plan"], "virtual_point", a.kwargs["context"]
    )
    a.rows = [dict(a.ready, free_mib=32 * 1024 - 1)]
    seen = []

    def sleep(seconds):
        seen.append(a.status())
        a.clock.sleep(seconds)
        a.rows = [a.ready]

    a.kwargs["sleep"] = sleep
    assert subject.wait_for_pre_cuda_admission(**a.kwargs) is a.ready
    assert seen[0]["phase"] == "WAITING"
    assert seen[0]["reason"] == "insufficient_phase_free_gpu_memory"
    assert seen[0]["worker_slot_retained"] is True and seen[0]["gpu_lease_retained"] is True
    assert a.status()["waiting_seconds"] == 2
    assert seen[0]["pid"] == a.status()["pid"] == os.getpid()
    assert a.status()["deadline_epoch"] == 1010


def test_existing_virtual_uses_24_not_first_sampling_32(admission):
    a = admission
    a.kwargs["context"]["feedback"]["mode"] = "sealed_existing"
    a.ready["free_mib"] = 24 * 1024
    assert subject.wait_for_pre_cuda_admission(**a.kwargs) is a.ready
    assert a.status()["memory_phase"] == "virtual_existing"
    assert a.status()["minimum_free_mib"] == 24 * 1024


def test_low_memory_wait_never_resets_phase_deadline(admission):
    a = admission
    a.ready["free_mib"] = 32 * 1024 - 1
    a.kwargs["deadline_epoch"] = 1003
    with pytest.raises(subject.AdmissionDeadlineExceeded):
        subject.wait_for_pre_cuda_admission(**a.kwargs)
    assert a.clock.now == 1003
    assert a.status()["phase"] == "TIMED_OUT" and a.status()["waiting_seconds"] == 3


@pytest.mark.parametrize(
    "mutation,match",
    [
        ("missing", "missing"),
        ("uuid", "UUID changed"),
        ("processes", "process observation"),
        ("pid", "process identity"),
        ("own", "unexpectedly owns"),
        ("duplicate", "duplicate identities"),
    ],
)
def test_invalid_identity_is_hard_failure_not_shared_admission(admission, mutation, match):
    a = admission
    if mutation == "missing":
        a.rows = []
    elif mutation == "uuid":
        a.ready["uuid"] = "GPU-changed"
    elif mutation == "processes":
        del a.ready["processes"]
    elif mutation == "pid":
        a.ready["processes"] = [{"pid": True}]
    elif mutation == "own":
        a.ready["processes"] = [{"pid": os.getpid()}]
    else:
        a.ready["processes"] = [{"pid": 42}, {"pid": 42}]
    with pytest.raises(subject.AdmissionError, match=match):
        subject.wait_for_pre_cuda_admission(**a.kwargs)
    assert a.clock.now == 1000 and a.status()["phase"] == "FAILED"


@pytest.mark.parametrize("field", ["rss", "peak_rss", "available", "process_missing"])
def test_ram_guards_are_not_relaxed(admission, field):
    a = admission
    setattr(
        a,
        field,
        True if field == "process_missing" else 0 if field == "available" else 193 * subject.GIB,
    )
    with pytest.raises(subject.AdmissionError):
        subject.wait_for_pre_cuda_admission(**a.kwargs)


def test_shard_still_uses_160_gib_rss(admission):
    a = admission
    a.kwargs["stage"] = "shard00"
    a.rss = a.peak_rss = 161 * subject.GIB
    with pytest.raises(subject.AdmissionError, match="RSS"):
        subject.wait_for_pre_cuda_admission(**a.kwargs)


@pytest.mark.parametrize("kind", ["stop", "cuda"])
def test_wait_rechecks_legal_stop_and_cuda_before_admitting(admission, kind):
    a = admission
    a.rows = [dict(a.ready, free_mib=1)]

    def sleep(seconds):
        a.clock.sleep(seconds)
        a.rows = [a.ready]
        a.stopped = kind == "stop"
        a.initialized = kind == "cuda"

    a.kwargs["sleep"] = sleep
    with pytest.raises(subject.AdmissionStopped if kind == "stop" else subject.AdmissionError):
        subject.wait_for_pre_cuda_admission(**a.kwargs)
    assert a.status()["phase"] == ("STOPPED" if kind == "stop" else "FAILED")


def test_reader_latency_cannot_admit_after_deadline(admission):
    a = admission

    def inventory():
        a.clock.now = 1011
        return [a.ready]

    a.kwargs["inventory"] = inventory
    with pytest.raises(subject.AdmissionDeadlineExceeded):
        subject.wait_for_pre_cuda_admission(**a.kwargs)
    assert a.status()["phase"] == "TIMED_OUT"


def test_context_and_fixed_policy_cannot_be_relabelled(admission):
    a = admission
    a.kwargs["context"]["id"] = "another-point"
    with pytest.raises(subject.AdmissionError, match="context identity"):
        subject.wait_for_pre_cuda_admission(**a.kwargs)
    a.kwargs["context"]["id"] = a.kwargs["context_id"]
    a.kwargs["plan"]["gpu_admission_policy"]["minimum_free_gib_by_phase"]["train"] = 1
    with pytest.raises(subject.AdmissionError, match="policy"):
        subject.wait_for_pre_cuda_admission(**a.kwargs)


def test_no_second_admission_attempt_reuses_heartbeat(admission):
    a = admission
    subject.wait_for_pre_cuda_admission(**a.kwargs)
    with pytest.raises(subject.AdmissionError, match="already exists"):
        subject.wait_for_pre_cuda_admission(**a.kwargs)
