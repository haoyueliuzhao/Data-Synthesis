"""Focused CPU/mock resource lifetime controls; no CUDA or model is loaded."""

import fcntl
import os
import signal
import subprocess
import sys
from types import SimpleNamespace

import pytest

import finqa_v54_runtime as runtime


class FakeCuda:
    def __init__(self):
        self.initialized = False
        self.allocated = self.reserved = self.peak = self.peak_reserved = 0
        self.free = 70 * runtime.GIB
        self.resets = 0
        self.memory = SimpleNamespace(get_allocator_backend=lambda: "native")

    def is_initialized(self):
        return self.initialized

    def set_device(self, device):
        assert device == 0
        self.initialized = True

    def reset_peak_memory_stats(self):
        self.resets += 1
        self.peak, self.peak_reserved = self.allocated, self.reserved

    def synchronize(self):
        pass

    def mem_get_info(self):
        return self.free, 80 * runtime.GIB

    def memory_allocated(self):
        return self.allocated

    def memory_reserved(self):
        return self.reserved

    def max_memory_allocated(self):
        return self.peak

    def max_memory_reserved(self):
        return self.peak_reserved


@pytest.fixture
def environment(tmp_path, monkeypatch):
    lease_root = tmp_path / "leases"
    lease_root.mkdir()
    lease_path = lease_root / ("gpu-" + runtime.digest(runtime.GPU_UUIDS["0"]) + ".lock")
    lease = lease_path.open("a")
    fcntl.flock(lease, fcntl.LOCK_EX | fcntl.LOCK_NB)
    protocol = runtime.publish(tmp_path / "protocol/record.json", dict(
        resource_policy=runtime.resource_policy(), allowed_gpu_indices=list(range(8)),
        gpu_uuids=runtime.GPU_UUIDS, gpu_lease_root=str(lease_root)))
    cuda = FakeCuda()
    capacity = dict(available_bytes=512 * runtime.GIB)
    process = dict(rss_bytes=2 * runtime.GIB, peak_rss_bytes=3 * runtime.GIB)
    row = dict(index=0, uuid=runtime.GPU_UUIDS["0"], free_mib=70 * 1024)
    monkeypatch.setattr(runtime, "inventory", lambda: [dict(row)])
    monkeypatch.setattr(runtime, "host_memory", lambda: dict(capacity))
    monkeypatch.setattr(runtime, "process_memory", lambda pid: dict(process))
    monkeypatch.setattr(runtime, "birth", lambda pid: "test-birth")
    monkeypatch.setenv("CUDA_VISIBLE_DEVICES", runtime.GPU_UUIDS["0"])
    monkeypatch.setenv("V54_GPU_LEASE_FD", str(lease.fileno()))

    def make(stage="train_Hold", kind="train"):
        job = dict(id="seed137." + stage, seed=137, stage=stage, kind=kind)
        monkeypatch.setenv("V54_JOB_ID", job["id"])
        return runtime.ResourceGuard(tmp_path, job, 0, torch_module=SimpleNamespace(cuda=cuda))

    yield SimpleNamespace(root=tmp_path, make=make, cuda=cuda, lease=lease,
                          lease_path=lease_path, protocol=protocol, process=process,
                          capacity=capacity, row=row)
    lease.close()


def test_phase_classification_matches_worker_and_eval_and_rejects_wrong_threshold():
    expected = {**{f"shard{i:02d}": "class_" for i in range(4)},
                "feedback_C05": "feedback", "replay_C05": "replay",
                "distribution_C05": "distribution", "generate": "generate",
                **{f"train_{arm}": "train" for arm in ("Hold", "C1", "C05")}}
    for stage, kind in expected.items():
        assert runtime.kind(dict(stage=stage, memory_phase=kind)) == kind
    with pytest.raises(ValueError, match="phase differ"):
        runtime.kind(dict(stage="replay_C05", kind="train"))
    with pytest.raises(ValueError, match="unregistered"):
        runtime.kind(dict(stage="unknown", kind="train"))


def test_native_lifetime_resets_once_restores_hooks_and_retains_lease_until_exit(environment):
    f = environment
    guard = f.make()
    original_reset = f.cuda.reset_peak_memory_stats
    original_handler = signal.getsignal(signal.SIGTERM)
    with guard:
        assert f.cuda.resets == 1
        assert guard.lease_identity["inode"] == os.fstat(f.lease.fileno()).st_ino
        with pytest.raises(runtime.ResourceGateError, match="peak reset forbidden"):
            f.cuda.reset_peak_memory_stats()
        f.cuda.allocated, f.cuda.peak = 10 * runtime.GIB, 60 * runtime.GIB
        guard.check("model_loaded")
        f.cuda.allocated = 0
    closeout = runtime.checked(guard.directory / "closeout/record.json")
    assert closeout["status"] == "COMPLETE"
    assert closeout["resources"] == guard.report()
    assert closeout["resources"]["peak_allocated_bytes"] == 60 * runtime.GIB
    assert closeout["resources"]["peak_resets_before_loading"] == 1
    assert f.cuda.reset_peak_memory_stats == original_reset
    assert signal.getsignal(signal.SIGTERM) == original_handler
    assert guard._events.closed and not guard._thread.is_alive()
    with f.lease_path.open("a") as independent:
        with pytest.raises(BlockingIOError):
            fcntl.flock(independent, fcntl.LOCK_EX | fcntl.LOCK_NB)


def test_historical_peak_cannot_be_hidden_by_small_current_allocation(environment):
    f = environment
    guard = f.make()
    with pytest.raises(runtime.ResourceGateError, match="resource gate failed"):
        with guard:
            f.cuda.allocated, f.cuda.peak = runtime.GIB, 77 * runtime.GIB
            guard.check("after_release")
    closeout = runtime.checked(guard.directory / "closeout/record.json")
    assert closeout["status"] == "FAILED_OR_STOPPED"
    assert closeout["resources"]["peak_allocated_bytes"] == 77 * runtime.GIB
    assert not closeout["resources"]["all_gates_passed"]
    assert f.cuda.resets == 1


def test_failure_at_final_boundary_still_seals_failed_closeout(environment):
    f = environment
    guard = f.make()
    with pytest.raises(runtime.ResourceGateError):
        with guard:
            f.cuda.free = runtime.GIB
    closeout = runtime.checked(guard.directory / "closeout/record.json")
    assert closeout["status"] == "FAILED_OR_STOPPED"
    assert closeout["error"]["type"] == "ResourceGateError"
    assert guard.observations[-1]["label"] == "worker_final_boundary"
    assert guard._events.closed


def test_pre_cuda_capacity_wait_does_no_model_work_or_extra_peak_reset(environment, monkeypatch):
    f = environment
    f.row["free_mib"] = (runtime.MINIMUM_FREE_GIB["train"] - 1) * 1024
    waits = []

    def release_capacity(seconds):
        waits.append(seconds)
        assert not f.cuda.initialized
        f.row["free_mib"] = 70 * 1024

    monkeypatch.setattr(runtime.time, "sleep", release_capacity)
    with f.make() as guard:
        assert waits == [2]
        assert f.cuda.resets == 1
    assert guard.report()["all_gates_passed"]


def test_hard_host_peak_fails_instead_of_waiting_forever_before_cuda(environment, monkeypatch):
    f = environment
    f.process["peak_rss_bytes"] = 193 * runtime.GIB
    monkeypatch.setattr(runtime.time, "sleep", lambda _: pytest.fail("lifetime peak cannot recover"))
    guard = f.make()
    with pytest.raises(runtime.ResourceGateError, match="historical RSS"):
        with guard:
            pytest.fail("a failed lifetime resource gate cannot load a model")
    assert not f.cuda.initialized and f.cuda.resets == 0
    assert runtime.checked(guard.directory / "closeout/record.json")["status"] == "FAILED_OR_STOPPED"


def test_open_but_unlocked_descriptor_is_not_an_inherited_gpu_lease(environment):
    f = environment
    fcntl.flock(f.lease, fcntl.LOCK_UN)
    guard = f.make()
    with pytest.raises(ValueError, match="held exclusive flock"):
        with guard:
            pytest.fail("unowned device cannot initialize CUDA")
    assert not f.cuda.initialized
    assert runtime.checked(guard.directory / "closeout/record.json")["status"] == "FAILED_OR_STOPPED"


def test_actual_exec_child_observes_parent_flock_on_inherited_descriptor(environment):
    f = environment
    child = subprocess.run([sys.executable, "-c",
        "from pathlib import Path; import sys; "
        "rows=Path('/proc/self/fdinfo/'+sys.argv[1]).read_text().splitlines(); "
        "assert any(r.startswith('lock:') and 'FLOCK' in r and 'WRITE' in r for r in rows)",
        str(f.lease.fileno())], pass_fds=(f.lease.fileno(),), capture_output=True, text=True)
    assert child.returncode == 0, child.stderr


@pytest.mark.parametrize("stage,kind", [("train_Hold", "train"), ("replay_C05", "replay")])
def test_explicit_stop_is_terminal_but_replay_can_save_a_response_first(environment, stage, kind):
    f = environment
    guard = f.make(stage, kind)
    with pytest.raises(runtime.ExplicitStop):
        with guard:
            guard._signal(signal.SIGTERM, None)
            if kind == "replay":
                # The R3 accumulator may finish and durably checkpoint this
                # response; a clean final exit still cannot claim success.
                guard.check("replay_complete_response_checkpoint")
            else:
                guard.check("before_next_sft_update")
    closeout = runtime.checked(guard.directory / "closeout/record.json")
    assert closeout["status"] == "FAILED_OR_STOPPED"
    assert closeout["error"]["type"] == "ExplicitStop"
    assert closeout["resources"]["received_signals"][0]["signal"] == signal.SIGTERM
