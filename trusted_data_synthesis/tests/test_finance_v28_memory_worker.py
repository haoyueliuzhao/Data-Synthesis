"""CPU-only controls for same-worker reusable CUDA cache reservation."""

import importlib.util
import json
import os
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest

SCRIPT = Path(__file__).resolve().parents[1] / "scripts/finqa_v28_memory_worker.py"
SPEC = importlib.util.spec_from_file_location("v28_memory_worker_tests", SCRIPT)
worker = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(worker)


class FakeTensor:
    def __init__(self, torch, count):
        self.torch, self.count = torch, count

    def __del__(self):
        self.torch.allocated -= self.count


class FakeTorch:
    """No RNG APIs exist; a reservation invoking one fails the CPU test."""

    uint8 = "uint8"

    def __init__(self):
        self.allocated = self.reserved = 0
        self.initialized = False
        self.events = []
        self.cuda = SimpleNamespace(
            is_initialized=lambda: self.initialized,
            memory=SimpleNamespace(get_allocator_backend=lambda: "native"),
            memory_reserved=lambda index: self.reserved,
            memory_allocated=lambda index: self.allocated,
            synchronize=lambda: self.events.append("synchronize"),
        )

    def empty(self, count, *, dtype, device):
        assert dtype == "uint8" and device == "cuda:0"
        self.initialized = True
        self.events.append(("empty", count))
        self.allocated += count
        self.reserved = max(self.reserved, self.allocated)
        return FakeTensor(self, count)


def snapshot(*, processes=(), free=81154, uuid="GPU-fixture"):
    return {
        "gpu_index": 7, "uuid": uuid, "total_mib": 81920, "free_mib": free,
        "compute_processes": [{"pid": pid, "used_mib": 1} for pid in processes],
    }


@pytest.fixture
def setup(tmp_path, monkeypatch):
    monkeypatch.setenv("CUDA_VISIBLE_DEVICES", "GPU-fixture")
    for name in ("PYTORCH_CUDA_ALLOC_CONF", "PYTORCH_ALLOC_CONF",
                 "PYTORCH_NO_CUDA_MEMORY_CACHING"):
        monkeypatch.delenv(name, raising=False)
    monkeypatch.setattr(worker, "gpu_snapshot", lambda index: snapshot())
    return SimpleNamespace(torch=FakeTorch(), receipts=tmp_path, uuid="GPU-fixture")


def test_reserve_uses_no_rng_and_keeps_reusable_cache_not_tensor(setup):
    c = setup
    worker.reserve_cache(c.torch, 7, c.uuid, c.receipts)
    assert c.torch.allocated == 0
    assert c.torch.reserved == worker.RESERVATION_BYTES
    assert c.torch.events == [("empty", 76 * 1024**3), "synchronize"]
    receipt = json.loads((c.receipts / "reserved.json").read_text())
    assert receipt["hardware_compute_exclusive"] is False
    assert receipt["reservation_tensor_retained"] is False
    assert receipt["id"] == worker.digest({k: v for k, v in receipt.items() if k != "id"})


@pytest.mark.parametrize("kind", ["train", "eval"])
def test_loader_preserves_arguments_result_calls_and_postload_cache(setup, kind):
    c = setup
    args, kwargs, result, events = (object(), object()), {"seed": 251}, object(), []

    def original(*passed, **named):
        assert passed == args and named == kwargs
        assert c.torch.reserved == worker.RESERVATION_BYTES and c.torch.allocated == 0
        events.append("loaded")
        c.torch.allocated = 10 * 1024**3
        return result

    rt = SimpleNamespace(torch=c.torch)
    if kind == "train":
        module = SimpleNamespace(__name__="finqa_v25_training_replication")
        rt.launcher = SimpleNamespace(_load_components=original)
    else:
        module = SimpleNamespace(__name__="finqa_v25_evaluation")
        rt.load_final_provider = original
    owner, attribute, saved, state = worker.install_loader_hook(
        module, rt, 7, c.uuid, c.receipts
    )
    assert saved is original
    assert getattr(owner, attribute)(*args, **kwargs) is result
    assert events == ["loaded"] and state == {"calls": 1, "loader_calls": 1}
    receipt = json.loads((c.receipts / "model_loaded.json").read_text())
    assert receipt["post_load_refill_bytes"] == 0
    with pytest.raises(ValueError, match="one original"):
        getattr(owner, attribute)(*args, **kwargs)


def test_postload_refill_uses_target_minus_allocated_not_reserved(setup):
    c = setup
    c.torch.reserved, c.torch.allocated = 30 * 1024**3, 20 * 1024**3
    worker.maintain_loaded_cache(c.torch, 7, c.uuid, c.receipts)
    assert c.torch.events[0] == ("empty", 56 * 1024**3)
    assert c.torch.reserved == worker.RESERVATION_BYTES
    assert c.torch.allocated == 20 * 1024**3


@pytest.mark.parametrize("bad", ["unmapped", "initialized", "allocator", "caching", "free",
                                 "foreign", "UUID"])
def test_bad_admission_fails_before_cuda_allocation(setup, monkeypatch, bad):
    c = setup
    if bad == "unmapped":
        monkeypatch.delenv("CUDA_VISIBLE_DEVICES")
    elif bad == "initialized":
        c.torch.initialized = True
    elif bad == "allocator":
        monkeypatch.setenv("PYTORCH_CUDA_ALLOC_CONF", "max_split_size_mb:128")
    elif bad == "caching":
        monkeypatch.setenv("PYTORCH_NO_CUDA_MEMORY_CACHING", "1")
    elif bad == "free":
        monkeypatch.setattr(worker, "gpu_snapshot", lambda index: snapshot(free=79000))
    elif bad == "foreign":
        monkeypatch.setattr(worker, "gpu_snapshot", lambda index: snapshot(processes=[987654]))
    else:
        monkeypatch.setattr(worker, "gpu_snapshot", lambda index: snapshot(uuid="GPU-changed"))
    with pytest.raises(ValueError):
        worker.reserve_cache(c.torch, 7, c.uuid, c.receipts)
    assert c.torch.events == []


def test_foreign_process_arriving_during_reservation_fails_closed(setup, monkeypatch):
    samples = iter([snapshot(), snapshot(processes=[os.getpid(), 987654])])
    monkeypatch.setattr(worker, "gpu_snapshot", lambda index: next(samples))
    with pytest.raises(ValueError, match="foreign compute"):
        worker.reserve_cache(setup.torch, 7, setup.uuid, setup.receipts)
    assert not (setup.receipts / "reserved.json").exists()


def test_allocation_failure_does_not_call_model_loader(setup):
    c = setup

    def failed(*args, **kwargs):
        raise RuntimeError("fixture allocation failure")

    c.torch.empty = failed
    rt = SimpleNamespace(
        torch=c.torch, launcher=SimpleNamespace(_load_components=lambda: pytest.fail("loaded"))
    )
    owner, attribute, _, state = worker.install_loader_hook(
        SimpleNamespace(__name__="finqa_v25_training_replication"),
        rt, 7, c.uuid, c.receipts,
    )
    with pytest.raises(RuntimeError, match="fixture allocation failure"):
        getattr(owner, attribute)()
    assert state["loader_calls"] == 0
    assert json.loads((c.receipts / "loader_failure.json").read_text())["automatic_retry"] is False


def test_original_cli_is_preserved_and_no_allocation_before_worker_admission(setup, monkeypatch):
    c = setup
    c.receipts = c.receipts / "receipt"
    command = ["train", "--seed", "251", "--arm", "c_only", "--gpu-index", "7", "--resume"]
    path = Path("/fixture/implementation/finqa_v25_training_replication.py")
    monkeypatch.setattr(worker, "checked_worker", lambda p, a: (p, 7, {"fixture": True}))
    module = SimpleNamespace(__name__="finqa_v25_training_replication")
    rt = SimpleNamespace(torch=c.torch, launcher=SimpleNamespace(_load_components=lambda: 5))
    module.load_runtime = lambda: rt

    def original_main():
        assert sys.argv == [str(path), *command]
        assert c.torch.events == []  # original admission precedes any reservation
        assert rt.launcher._load_components() == 5

    module.main = original_main
    monkeypatch.setattr(worker, "load_worker", lambda p: module)
    old_argv = sys.argv
    worker.main(["--worker", str(path), "--receipt-dir", str(c.receipts),
                 "--memory-mode", "high_cache", "--", *command])
    assert sys.argv is old_argv
    assert (c.receipts / "worker_returned.json").is_file()


def test_gpu_query_parses_exact_physical_index_and_processes(monkeypatch):
    calls = []

    def run(command, **kwargs):
        calls.append(command)
        output = "GPU-fixture, 81920, 81154\n" if len(calls) == 1 else "GPU-fixture, 123, 2048\n"
        return SimpleNamespace(stdout=output)

    monkeypatch.setattr(worker.subprocess, "run", run)
    result = worker.gpu_snapshot(7)
    assert result["compute_processes"] == [{"pid": 123, "used_mib": 2048}]
    assert all(command[1:3] == ["-i", "7"] for command in calls)


@pytest.fixture
def source_tree(tmp_path, monkeypatch):
    implementation = tmp_path / "implementation"
    implementation.mkdir()
    hashes = {}
    for name in worker.WORKER_HASHES:
        path = implementation / name
        path.write_text("# frozen CPU source " + name)
        hashes[name] = worker.file_reference(path)["sha256"]
    monkeypatch.setattr(worker, "WORKER_HASHES", hashes)
    manifest = {"sha256": hashes, "scientific_runtime": "/fixture/frozen"}
    manifest["id"] = worker.digest(manifest)
    (implementation / "record.json").write_text(json.dumps(manifest))
    protocol = {"implementation_id": manifest["id"]}
    protocol["id"] = worker.digest(protocol)
    (tmp_path / "protocol").mkdir()
    (tmp_path / "protocol/record.json").write_text(json.dumps(protocol))
    return implementation


def test_source_binding_preserves_original_frozen_identity(source_tree):
    path = source_tree / "finqa_v25_training_replication.py"
    actual, index, binding = worker.checked_worker(path, ["train", "--gpu-index", "7"])
    assert actual == path and index == 7
    assert binding["sources"][path.name]["sha256"] == worker.WORKER_HASHES[path.name]


@pytest.mark.parametrize("change", ["source", "dependency", "manifest", "protocol", "CLI"])
def test_changed_source_manifest_or_scientific_command_rejected(source_tree, change):
    path = source_tree / "finqa_v25_training_replication.py"
    args = ["train", "--gpu-index", "7"]
    if change == "source":
        path.write_text("modified worker")
    elif change == "dependency":
        (source_tree / "finqa_v23_test_confirmation.py").write_text("modified dependency")
    elif change == "manifest":
        (source_tree / "record.json").write_text(json.dumps({"id": "changed"}))
    elif change == "protocol":
        (source_tree.parent / "protocol/record.json").write_text(json.dumps({"id": "changed"}))
    else:
        args[0] = "prepare"
    with pytest.raises(ValueError):
        worker.checked_worker(path, args)


def test_postload_foreign_process_rejects_return(setup, monkeypatch):
    c = setup
    c.torch.reserved = worker.RESERVATION_BYTES
    monkeypatch.setattr(worker, "gpu_snapshot", lambda index: snapshot(processes=[987654]))
    with pytest.raises(ValueError, match="foreign compute"):
        worker.maintain_loaded_cache(c.torch, 7, c.uuid, c.receipts)
    assert not (c.receipts / "model_loaded.json").exists()


@pytest.mark.parametrize("fails", [False, True])
def test_shared_mode_preserves_original_worker_without_hook_or_reservation(
    setup, monkeypatch, fails
):
    c = setup
    path = Path("/fixture/implementation/finqa_v25_training_replication.py")
    command = ["train", "--seed", "251", "--gpu-index", "7", "--arm", "static"]
    monkeypatch.setattr(worker, "checked_worker", lambda p, a: (p, 7, {"fixture": True}))
    monkeypatch.setattr(worker, "gpu_snapshot",
                        lambda index: snapshot(processes=[987654], free=52000))
    monkeypatch.setattr(worker, "install_loader_hook", lambda *a: pytest.fail("shared hook"))
    monkeypatch.setattr(worker, "reserve_cache", lambda *a: pytest.fail("shared reservation"))
    receipts = c.receipts / "shared"
    calls = []

    def original_main():
        assert sys.argv == [str(path), *command]
        assert c.torch.events == []
        calls.append("original-main")
        if fails:
            raise RuntimeError("original resource failure")

    module = SimpleNamespace(main=original_main)  # no load_runtime needed in shared mode
    monkeypatch.setattr(worker, "load_worker", lambda p: module)
    arguments = ["--worker", str(path), "--receipt-dir", str(receipts),
                 "--memory-mode", "shared_checkpointed", "--", *command]
    if fails:
        with pytest.raises(RuntimeError, match="original resource failure"):
            worker.main(arguments)
        result = json.loads((receipts / "worker_failure.json").read_text())
        assert result["automatic_retry"] is False
    else:
        worker.main(arguments)
        result = json.loads((receipts / "worker_returned.json").read_text())
        assert result["reservation_performed"] is False
    intent = json.loads((receipts / "wrapper_intent.json").read_text())
    assert intent["memory_mode"] == "shared_checkpointed" and intent["reservation_bytes"] == 0
    assert intent["original_worker_GPU_admission_preserved"] is True
    assert intent["checkpoint_policy"]["resume_requires_explicit_safe_boundary_proof"] is True
    assert calls == ["original-main"]


def test_high_cache_does_not_silently_fall_back_to_shared(setup, monkeypatch):
    path = Path("/fixture/implementation/finqa_v25_training_replication.py")
    monkeypatch.setattr(worker, "checked_worker", lambda p, a: (p, 7, {"fixture": True}))
    monkeypatch.setattr(worker, "gpu_snapshot",
                        lambda index: snapshot(processes=[987654], free=52000))
    monkeypatch.setattr(worker, "load_worker", lambda p: pytest.fail("must not start shared"))
    with pytest.raises(ValueError, match="foreign compute"):
        worker.main(["--worker", str(path), "--receipt-dir", str(setup.receipts / "bad"),
                     "--memory-mode", "high_cache", "--", "train", "--gpu-index", "7"])


def test_memory_mode_must_be_explicit(setup):
    with pytest.raises(SystemExit):
        worker.main(["--worker", "/fixture/worker", "--receipt-dir", str(setup.receipts),
                     "--", "train", "--gpu-index", "7"])
