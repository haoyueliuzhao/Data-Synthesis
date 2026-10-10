"""CPU/mock checks for the V36 adapter, never a production GPU validation."""

import ast
import hashlib
import importlib
import json
import os
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest

sys.path.insert(0, str(Path(__file__).parents[1] / "scripts"))
worker = importlib.import_module("finqa_v36_worker")


def require(ok, message):
    if not ok:
        raise ValueError(message)


def seal(body):
    raw = json.dumps(body, sort_keys=True, separators=(",", ":")).encode()
    return dict(body, id=hashlib.sha256(raw).hexdigest())


@pytest.fixture
def admission(tmp_path, monkeypatch):
    root = tmp_path / "recovery_02"
    original_path = root / "implementation/finqa_v35_task_worker.py"
    original_path.parent.mkdir(parents=True)
    original_path.write_text("# byte-identical original fixture\n")
    original_bytes = original_path.read_bytes()
    calls = []
    manifest = dict(sha256={original_path.name: hashlib.sha256(original_bytes).hexdigest()})
    control = SimpleNamespace(
        __file__=str(root / "recovery_implementation/finqa_v36_controller.py"), require=require
    )

    def check(name, result):
        def checked(given):
            assert given == root
            calls.append(name)
            return result

        return checked

    control.checked_v36_implementation = check("control_manifest", {"id": "control"})
    protocol = {"id": "protocol", "cache_index": {"id": "index"}}
    control.checked_protocol = check("protocol", protocol)
    control.checked_math_implementation = check("math_manifest", manifest)
    published = []

    def publish(path, body):
        path = Path(path)
        if path.exists():
            raise FileExistsError(str(path))
        path.parent.mkdir(parents=True, exist_ok=True)
        record = seal(body)
        path.write_text(json.dumps(record))
        published.append((path, record))
        return record

    control.publish = publish
    control.now = lambda: "test-time"
    control.checked = lambda path: json.loads(Path(path).read_bytes())
    control.entry = lambda path: dict(
        path=str(path),
        sha256=hashlib.sha256(Path(path).read_bytes()).hexdigest(),
        id=control.checked(path)["id"],
    )
    cache_state = {}
    cache = SimpleNamespace(verification_summary=lambda: dict(cache_state))
    original_cache = SimpleNamespace(
        TaskCache=object(), TaskPoolView=object(), make_task_plan=object()
    )
    adapter = SimpleNamespace(
        TaskCache=lambda *_a, **_k: cache,
        TaskPoolView=original_cache.TaskPoolView,
        make_task_plan=original_cache.make_task_plan,
    )
    tail, values = object(), (object(), object(), object())

    def original_dependencies(given):
        assert given == root
        calls.append("original_dependencies")
        return tail, original_cache, values

    original = SimpleNamespace(
        __file__=str(original_path),
        control=control,
        dependencies=original_dependencies,
        execute_shard=object(),
        execute_coordinator=object(),
        checked_sources=object(),
        state_identity=object(),
    )
    result = dict(status="COMPLETE")

    def original_run(given, stage, gpu_index, deadline_epoch):
        calls.append(("original_run", given, stage, gpu_index, deadline_epoch))
        loaded_tail, loaded_cache_module, loaded_values = original.dependencies(given)
        assert loaded_tail is tail and loaded_values is values and loaded_cache_module is adapter
        loaded_cache_module.TaskCache()
        parent, local = (183, 0) if stage == "shard01" else (741, 3)
        cache_state.update(
            index_id="index",
            process_id=os.getpid(),
            parent_tasks_strictly_verified=parent,
            local_tasks_strictly_verified=local,
            strict_payload_file_reads=parent + local,
            verified_task_ids=[f"task{i}" for i in range(parent + local)],
            cross_process_verification_waiver=False,
            parent_gradient_payload_bytes_copied=0,
        )
        return control.publish(root / stage / "result/record.json", result)

    original.run = original_run

    def overlay_adapter(given, received_cache, received_control):
        assert given == root and received_cache is original_cache and received_control is control
        calls.append("overlay_adapter")
        return adapter

    overlay = SimpleNamespace(
        __file__=str(root / "recovery_implementation/finqa_v36_cache.py"),
        overlay_adapter=overlay_adapter,
    )

    def module(path, name):
        assert sys.modules[worker.ORIGINAL_CONTROL_NAME] is control
        if name == worker.ORIGINAL_WORKER_NAME:
            assert path == original_path
            calls.append("original_import")
            return original
        assert name == worker.CACHE_NAME and path == Path(overlay.__file__)
        calls.append("overlay_import")
        return overlay

    control._module = module
    monkeypatch.setattr(
        worker, "__file__", str(root / "recovery_implementation/finqa_v36_worker.py")
    )
    monkeypatch.setitem(sys.modules, worker.CONTROLLER_NAME, control)
    for name in (worker.ORIGINAL_CONTROL_NAME, worker.ORIGINAL_WORKER_NAME, worker.CACHE_NAME):
        monkeypatch.delitem(sys.modules, name, raising=False)
    monkeypatch.setattr(sys, "path", list(sys.path))
    yield SimpleNamespace(
        root=root,
        control=control,
        original=original,
        overlay=overlay,
        adapter=adapter,
        original_cache=original_cache,
        original_path=original_path,
        original_bytes=original_bytes,
        calls=calls,
        result=result,
        protocol=protocol,
        cache=cache,
        cache_state=cache_state,
        published=published,
    )
    for name in (worker.ORIGINAL_CONTROL_NAME, worker.ORIGINAL_WORKER_NAME, worker.CACHE_NAME):
        sys.modules.pop(name, None)


@pytest.mark.parametrize("stage,gpu", [("shard01", 4), ("coordinator", 7)])
def test_both_allowed_stages_run_original_functions_with_only_cache_slot_changed(
    admission, stage, gpu
):
    originals = {
        name: getattr(admission.original, name)
        for name in (
            "run",
            "execute_shard",
            "execute_coordinator",
            "checked_sources",
            "state_identity",
        )
    }
    result = worker.run(admission.root, stage, gpu, 1791613654.528971)
    assert result["status"] == admission.result["status"]
    receipt = admission.control.checked(result["cache_tensor_verification"]["path"])
    assert receipt["strict_payload_file_reads"] == (183 if stage == "shard01" else 744)
    assert admission.published[-2][0].parent.name == "cache_tensor_verification"
    assert admission.published[-1][0].parent.name == "result"
    assert admission.calls == [
        "control_manifest",
        "protocol",
        "math_manifest",
        "original_import",
        "overlay_import",
        ("original_run", admission.root, stage, gpu, 1791613654.528971),
        "original_dependencies",
        "overlay_adapter",
    ]
    assert all(
        getattr(admission.original, name) is function for name, function in originals.items()
    )
    assert admission.original_path.read_bytes() == admission.original_bytes


@pytest.mark.parametrize(
    "stage,gpu",
    [("shard00", 3), ("shard02", 5), ("shard03", 7), ("shard01", 7), ("coordinator", 4)],
)
def test_other_shards_or_wrong_gpu_are_not_admitted(admission, stage, gpu):
    with pytest.raises(ValueError, match="only GPU4 shard01"):
        worker.run(admission.root, stage, gpu, 123)
    assert not admission.calls


@pytest.mark.parametrize("location", ["worker", "controller"])
def test_nonsealed_control_location_rejected(admission, monkeypatch, location):
    if location == "worker":
        monkeypatch.setattr(worker, "__file__", str(admission.root / "finqa_v36_worker.py"))
    else:
        admission.control.__file__ = str(admission.root / "finqa_v36_controller.py")
    with pytest.raises(ValueError, match="sealed V36"):
        worker.run(admission.root, "shard01", 4, 123)
    assert not admission.calls


@pytest.mark.parametrize(
    "method", ["checked_v36_implementation", "checked_math_implementation", "checked_protocol"]
)
def test_bad_source_or_authorization_rejected_before_math_import(admission, method):
    def fail(_root):
        raise ValueError("source admission failed")

    setattr(admission.control, method, fail)
    with pytest.raises(ValueError, match="source admission failed"):
        worker.run(admission.root, "coordinator", 7, 123)
    assert "original_import" not in admission.calls


def test_changed_original_math_worker_is_not_used(admission):
    admission.original_path.write_text("# altered\n")
    with pytest.raises(ValueError, match="worker bytes changed"):
        worker.run(admission.root, "coordinator", 7, 123)
    assert "original_import" not in admission.calls


@pytest.mark.parametrize("name", [worker.ORIGINAL_CONTROL_NAME, worker.ORIGINAL_WORKER_NAME])
def test_existing_unbound_modules_are_rejected(admission, monkeypatch, name):
    monkeypatch.setitem(sys.modules, name, object())
    with pytest.raises(ValueError, match="already imported|fresh original"):
        worker.run(admission.root, "coordinator", 7, 123)
    assert "original_import" not in admission.calls


@pytest.mark.parametrize("attribute", ["TaskPoolView", "make_task_plan"])
def test_overlay_must_not_change_pool_or_mathematical_plan(admission, attribute):
    setattr(admission.adapter, attribute, object())
    with pytest.raises(ValueError, match="must not replace task views"):
        worker.run(admission.root, "coordinator", 7, 123)


def test_original_source_or_numeric_resource_error_has_no_retry(admission):
    def fail(*_args):
        raise RuntimeError("original point/resource admission failed")

    admission.original.run = fail
    with pytest.raises(RuntimeError, match="original point/resource"):
        worker.run(admission.root, "coordinator", 7, 123)
    assert admission.calls.count("original_import") == 1


def test_postinstallation_numerical_function_mutation_is_rejected(admission):
    worker.install_overlay_dependency(
        admission.original, admission.root, admission.overlay, admission.control
    )
    admission.original.execute_coordinator = object()
    with pytest.raises(ValueError, match="scientific worker functions changed"):
        admission.original.dependencies(admission.root)


def test_dependency_adapter_cannot_redirect_to_another_root(admission):
    worker.install_overlay_dependency(
        admission.original, admission.root, admission.overlay, admission.control
    )
    with pytest.raises(ValueError, match="foreign overlay"):
        admission.original.dependencies(admission.root / "other")


def verification_state(admission, *, parent=183, local=0):
    admission.cache_state.update(
        index_id="index",
        process_id=os.getpid(),
        parent_tasks_strictly_verified=parent,
        local_tasks_strictly_verified=local,
        strict_payload_file_reads=parent + local,
        verified_task_ids=[f"task{i}" for i in range(parent + local)],
        cross_process_verification_waiver=False,
        parent_gradient_payload_bytes_copied=0,
    )


def test_partial_verification_cannot_publish_success_but_is_saved_on_failure(admission):
    verification_state(admission, parent=182)
    worker.install_verification_publisher(
        admission.control, admission.root, "shard01", admission.protocol, [admission.cache]
    )
    with pytest.raises(ValueError, match="exact actual cache"):
        admission.control.publish(
            admission.root / "shard01/result/record.json", {"status": "COMPLETE"}
        )
    assert not admission.published
    terminal = admission.control.publish(
        admission.root / "shard01/failure/record.json", {"error": "failed"}
    )
    receipt = admission.control.checked(terminal["cache_tensor_verification"]["path"])
    assert receipt["parent_tasks_strictly_verified"] == 182
    assert receipt["numerical_or_resource_acceptance_not_implied"] is True


def test_receipt_written_once_before_failed_result_publish_and_reused_by_failure(admission):
    verification_state(admission)
    ordinary_publish = admission.control.publish

    def fail_result(path, body):
        if Path(path).parent.name == "result":
            raise OSError("result publication failed")
        return ordinary_publish(path, body)

    admission.control.publish = fail_result
    worker.install_verification_publisher(
        admission.control, admission.root, "shard01", admission.protocol, [admission.cache]
    )
    with pytest.raises(OSError, match="publication failed"):
        admission.control.publish(
            admission.root / "shard01/result/record.json", {"status": "COMPLETE"}
        )
    receipt_path = admission.root / "shard01/cache_tensor_verification/record.json"
    original_bytes = receipt_path.read_bytes()
    terminal = admission.control.publish(
        admission.root / "shard01/failure/record.json", {"error": "publication failed"}
    )
    assert receipt_path.read_bytes() == original_bytes
    assert sum(path == receipt_path for path, _ in admission.published) == 1
    assert (
        terminal["cache_tensor_verification"]["id"] == admission.control.checked(receipt_path)["id"]
    )


def test_existing_receipt_cannot_be_reused_with_different_actual_summary(admission):
    verification_state(admission)
    worker.install_verification_publisher(
        admission.control, admission.root, "shard01", admission.protocol, [admission.cache]
    )
    admission.control.publish(admission.root / "shard01/result/record.json", {"status": "COMPLETE"})
    receipt = admission.root / "shard01/cache_tensor_verification/record.json"
    original = receipt.read_bytes()
    verification_state(admission, parent=182)
    with pytest.raises(ValueError, match="receipt differs"):
        admission.control.publish(
            admission.root / "shard01/failure/record.json", {"error": "later failure"}
        )
    assert receipt.read_bytes() == original
    assert not (admission.root / "shard01/failure/record.json").exists()


def test_failure_before_cache_construction_records_zero_reads_without_acceptance(admission):
    worker.install_verification_publisher(
        admission.control, admission.root, "shard01", admission.protocol, []
    )
    terminal = admission.control.publish(
        admission.root / "shard01/failure/record.json", {"error": "CPU source rejection"}
    )
    receipt = admission.control.checked(terminal["cache_tensor_verification"]["path"])
    assert receipt["cache_constructed"] is False and receipt["strict_payload_file_reads"] == 0


def test_nonterminal_publication_is_not_modified(admission):
    worker.install_verification_publisher(
        admission.control, admission.root, "coordinator", admission.protocol, []
    )
    body = {"comparison": {"same": True}}
    actual = admission.control.publish(
        admission.root / "coordinator/point_comparison/record.json", body
    )
    assert {k: v for k, v in actual.items() if k != "id"} == body
    assert not (admission.root / "coordinator/cache_tensor_verification/record.json").exists()


def test_wrapper_has_no_numerical_calls_tensor_load_or_deadline_reset():
    tree = ast.parse(Path(worker.__file__).read_text())
    calls = [
        node.func.attr
        for node in ast.walk(tree)
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute)
    ]
    assert calls.count("run") == 1
    assert not set(calls) & {
        "class_gradients",
        "class_gradients_with_cpu_saves",
        "prepare_virtual_point",
        "update_distribution",
        "load",
        "step",
        "reset_peak_memory_stats",
        "time",
        "monotonic",
    }
