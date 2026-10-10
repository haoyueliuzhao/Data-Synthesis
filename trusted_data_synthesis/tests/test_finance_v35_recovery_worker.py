"""CPU-only wrapper admission tests; the original worker is mocked, not run."""

import ast
import hashlib
import importlib
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest

sys.path.insert(0, str(Path(__file__).parents[1] / "scripts"))
worker = importlib.import_module("finqa_v35_recovery_worker")


def require(ok, message):
    if not ok:
        raise ValueError(message)


@pytest.fixture
def admission(tmp_path, monkeypatch):
    root = tmp_path / "recovery"
    original_path = root / "implementation/finqa_v35_task_worker.py"
    original_path.parent.mkdir(parents=True)
    original_path.write_text("# sealed original fixture\n")
    original_bytes = original_path.read_bytes()
    calls = []
    implementation = dict(sha256={original_path.name: hashlib.sha256(original_bytes).hexdigest()})
    recovery = SimpleNamespace(
        __file__=str(root / "recovery_implementation/finqa_v35_recovery_controller.py"),
        require=require,
    )

    def checked(name, result):
        def check(given_root):
            assert given_root == root
            calls.append(name)
            return result

        return check

    recovery.checked_recovery_implementation = checked("recovery_manifest", {"id": "recovery"})
    recovery.checked_protocol = checked("protocol", {"id": "new-protocol"})
    recovery.checked_math_implementation = checked("math_manifest", implementation)
    result = dict(status="COMPLETE", id="result")

    def original_run(given_root, stage, gpu_index, deadline_epoch):
        calls.append(("original_run", given_root, stage, gpu_index, deadline_epoch))
        return result

    original = SimpleNamespace(__file__=str(original_path), control=recovery, run=original_run)

    def module(path, name):
        assert path == original_path and name == worker.ORIGINAL_WORKER_NAME
        assert sys.modules[worker.ORIGINAL_CONTROL_NAME] is recovery
        calls.append("original_import")
        return original

    recovery._module = module
    monkeypatch.setattr(
        worker, "__file__", str(root / "recovery_implementation/finqa_v35_recovery_worker.py")
    )
    monkeypatch.setitem(sys.modules, worker.CONTROLLER_NAME, recovery)
    monkeypatch.delitem(sys.modules, worker.ORIGINAL_CONTROL_NAME, raising=False)
    monkeypatch.delitem(sys.modules, worker.ORIGINAL_WORKER_NAME, raising=False)
    # The wrapper mutates import state deliberately. Keep fixture isolation
    # even when the surrounding suite has already imported original modules.
    monkeypatch.setattr(sys, "path", list(sys.path))
    yield SimpleNamespace(
        root=root,
        recovery=recovery,
        original=original,
        original_path=original_path,
        original_bytes=original_bytes,
        calls=calls,
        implementation=implementation,
        result=result,
    )
    sys.modules.pop(worker.ORIGINAL_CONTROL_NAME, None)
    sys.modules.pop(worker.ORIGINAL_WORKER_NAME, None)


def test_validated_adapter_calls_unchanged_worker_once(admission):
    result = worker.run(admission.root, "shard01", 4, 1791613654.528971)
    assert result is admission.result
    assert admission.calls == [
        "recovery_manifest",
        "protocol",
        "math_manifest",
        "original_import",
        ("original_run", admission.root, "shard01", 4, 1791613654.528971),
    ]
    assert admission.original_path.read_bytes() == admission.original_bytes


@pytest.mark.parametrize("location", ["wrapper", "controller"])
def test_nonsealed_wrapper_or_controller_rejected_before_any_original_import(
    admission, monkeypatch, location
):
    if location == "wrapper":
        monkeypatch.setattr(
            worker, "__file__", str(admission.root / "implementation/finqa_v35_recovery_worker.py")
        )
    else:
        admission.recovery.__file__ = str(
            admission.root / "implementation/finqa_v35_recovery_controller.py"
        )
    with pytest.raises(ValueError, match="sealed recovery"):
        worker.run(admission.root, "shard01", 4, 123)
    assert not admission.calls


@pytest.mark.parametrize(
    "checker",
    ["checked_recovery_implementation", "checked_protocol", "checked_math_implementation"],
)
def test_invalid_manifest_or_authorization_never_imports_original(admission, checker):
    def fail(_root):
        raise ValueError("sealed admission failed")

    setattr(admission.recovery, checker, fail)
    with pytest.raises(ValueError, match="sealed admission failed"):
        worker.run(admission.root, "coordinator", 7, 123)
    assert "original_import" not in admission.calls


def test_changed_original_worker_is_rejected(admission):
    admission.original_path.write_text("# altered math fixture\n")
    with pytest.raises(ValueError, match="worker bytes changed"):
        worker.run(admission.root, "coordinator", 7, 123)
    assert "original_import" not in admission.calls


@pytest.mark.parametrize("module_name", [worker.ORIGINAL_CONTROL_NAME, worker.ORIGINAL_WORKER_NAME])
def test_preimported_other_controller_or_worker_is_not_reused(admission, monkeypatch, module_name):
    monkeypatch.setitem(sys.modules, module_name, SimpleNamespace())
    with pytest.raises(ValueError, match="already imported|fresh original"):
        worker.run(admission.root, "coordinator", 7, 123)
    assert "original_import" not in admission.calls


@pytest.mark.parametrize("binding", ["controller", "path"])
def test_imported_worker_must_bind_exact_adapter_and_source(admission, binding):
    if binding == "controller":
        admission.original.control = SimpleNamespace()
    else:
        admission.original.__file__ = str(admission.root / "different-worker.py")
    with pytest.raises(ValueError, match="did not bind"):
        worker.run(admission.root, "coordinator", 7, 123)
    assert not any(isinstance(call, tuple) for call in admission.calls)


def test_original_numerical_or_resource_failure_is_propagated_without_retry(admission):
    calls = []

    def fail(*args):
        calls.append(args)
        raise RuntimeError("original resource gate failed")

    admission.original.run = fail
    with pytest.raises(RuntimeError, match="original resource gate failed"):
        worker.run(admission.root, "coordinator", 7, 1791613654.528971)
    assert len(calls) == 1


def test_wrapper_has_no_mathematical_calls_or_deadline_reset():
    tree = ast.parse(Path(worker.__file__).read_text())
    attrs = [
        n.func.attr
        for n in ast.walk(tree)
        if isinstance(n, ast.Call) and isinstance(n.func, ast.Attribute)
    ]
    assert attrs.count("run") == 1
    assert not set(attrs) & {
        "prepare_virtual_point",
        "update_distribution",
        "class_gradients",
        "class_gradients_with_cpu_saves",
        "step",
        "reset_peak_memory_stats",
        "time",
        "monotonic",
    }
