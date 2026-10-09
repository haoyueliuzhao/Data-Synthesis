"""CPU/mock tests of the one-shot tail shell, not GPU numerical evidence."""

import ast
import copy
import hashlib
import importlib
import json
import os
import subprocess
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest
import torch

sys.path.insert(0, str(Path(__file__).parents[1] / "scripts"))
worker = importlib.import_module("finqa_v34_tail_worker")
immutable = importlib.import_module("trusted_synthesis.core.immutable_artifacts")


def digest(value):
    """Tiny tensor-aware fixture digest; no production runtime is imported."""
    if isinstance(value, torch.Tensor):
        raw = value.detach().cpu().contiguous()
        return digest(
            dict(
                shape=list(raw.shape),
                dtype=str(raw.dtype),
                bytes=raw.reshape(-1).view(torch.uint8).numpy().tobytes().hex(),
            )
        )
    if isinstance(value, dict):
        value = {str(key): digest(item) for key, item in value.items()}
    elif isinstance(value, (tuple, list)):
        value = [digest(item) for item in value]
    return hashlib.sha256(json.dumps(value, sort_keys=True).encode()).hexdigest()


@pytest.fixture
def saved(tmp_path):
    actual = dict(
        gJ={"weight": torch.tensor([[1.25, -2.5]], dtype=torch.float32)},
        pre_state={"rng": {"torch": torch.tensor([1, 2], dtype=torch.uint8)}},
    )
    state = dict(
        binding=dict(
            denominator=700,
            parameter_digest="parameters",
            point_id="point",
            cohort_seal_sha256="seal",
            reward_sha256="reward",
            response_count=573,
            backend_identity={"variant": "R3", "version": "sealed-V33"},
        ),
        cursor=573,
        accounting={"responses_replayed": 573},
        rng_digest=digest(actual["pre_state"]["rng"]),
        total=copy.deepcopy(actual["gJ"]),
    )
    checkpoint = dict(
        binding=copy.deepcopy(state["binding"]),
        cursor=573,
        full_replay_complete=True,
        response_prefix_complete=True,
    )
    runtime = SimpleNamespace(
        torch=torch,
        v8=SimpleNamespace(_tree_digest=digest, parameter_digest=digest),
    )

    def seal():
        path = tmp_path / "state.pt"
        torch.save(state, path)
        checkpoint["state_sha256"] = worker.control.sha(path)
        checkpoint["state_digest"] = digest(state)
        record = tmp_path / f"checkpoint{seal.count}" / "record.json"
        seal.count += 1
        worker.control.publish(record, checkpoint)
        return dict(
            source_final_checkpoint=worker.control.entry(record),
            source_final_checkpoint_state=worker.control.file_ref(path),
            saved_gJ_digest=digest(actual["gJ"]),
        )

    seal.count = 0
    return SimpleNamespace(
        actual=actual,
        state=state,
        checkpoint=checkpoint,
        rt=runtime,
        seal=seal,
    )


def test_saved_complete_gradient_read_from_checkpoint_with_zero_replay(saved):
    plan = saved.seal()
    gradient, report = worker.load_saved_gradient(plan, saved.rt, saved.actual)
    assert gradient is not saved.actual["gJ"]
    assert gradient["weight"].data_ptr() != saved.actual["gJ"]["weight"].data_ptr()
    assert torch.equal(gradient["weight"], saved.actual["gJ"]["weight"])
    assert report["reused_completed_responses"] == 573
    assert report["replayed_responses_this_supplement"] == 0
    assert report["denominator"] == 700
    assert report["receipt_validation_provenance"] == plan["source_final_checkpoint"]
    assert report["previously_validated_receipts_not_new_GPU_replay"] is True
    assert not torch.cuda.is_initialized()


def test_saved_accumulator_file_corruption_rejected_before_deserialization(saved, monkeypatch):
    plan = saved.seal()
    plan["source_final_checkpoint_state"]["sha256"] = "altered"
    monkeypatch.setattr(torch, "load", lambda *_a, **_k: pytest.fail("must not deserialize"))
    with pytest.raises(ValueError, match="accumulator bytes changed"):
        worker.load_saved_gradient(plan, saved.rt, saved.actual)


def test_saved_semantic_digest_is_checked_separately_from_file_hash(saved, monkeypatch):
    plan = saved.seal()
    real_load = torch.load

    def changed(*args, **kwargs):
        state = real_load(*args, **kwargs)
        state["accounting"]["responses_replayed"] = 572
        return state

    monkeypatch.setattr(torch, "load", changed)
    with pytest.raises(ValueError, match="state/cursor/point/RNG"):
        worker.load_saved_gradient(plan, saved.rt, saved.actual)


@pytest.mark.parametrize(
    "field",
    [
        "binding",
        "state_cursor",
        "record_cursor",
        "full_complete",
        "prefix_complete",
        "accounting",
        "denominator",
        "rng",
    ],
)
def test_completed_checkpoint_binding_and_rng_reject_changes(saved, field):
    if field == "binding":
        saved.state["binding"]["point_id"] = "different-point"
    elif field == "state_cursor":
        saved.state["cursor"] = 572
    elif field == "record_cursor":
        saved.checkpoint["cursor"] = 572
    elif field == "full_complete":
        saved.checkpoint["full_replay_complete"] = False
    elif field == "prefix_complete":
        saved.checkpoint["response_prefix_complete"] = False
    elif field == "accounting":
        saved.state["accounting"]["responses_replayed"] = 572
    elif field == "denominator":
        saved.state["binding"]["denominator"] = 573
        saved.checkpoint["binding"]["denominator"] = 573
    else:
        saved.state["rng_digest"] = "different-rng"
    with pytest.raises(ValueError, match="state/cursor/point/RNG"):
        worker.load_saved_gradient(saved.seal(), saved.rt, saved.actual)


@pytest.mark.parametrize("mutation", ["missing", "extra", "shape", "dtype", "nan", "inf", "value"])
def test_saved_gradient_coordinates_finiteness_and_values_reject_changes(saved, mutation):
    total = saved.state["total"]
    if mutation == "missing":
        total.clear()
    elif mutation == "extra":
        total["unexpected"] = torch.zeros(1)
    elif mutation == "shape":
        total["weight"] = total["weight"].reshape(2)
    elif mutation == "dtype":
        total["weight"] = total["weight"].double()
    elif mutation == "nan":
        total["weight"][0, 0] = float("nan")
    elif mutation == "inf":
        total["weight"][0, 0] = float("inf")
    else:
        total["weight"][0, 0] += 1
    message = (
        "coordinates"
        if mutation in {"missing", "extra"}
        else "original reference"
        if mutation == "value"
        else "invalid saved gradient"
    )
    with pytest.raises(ValueError, match=message):
        worker.load_saved_gradient(saved.seal(), saved.rt, saved.actual)


def test_saved_gradient_must_match_registered_digest_too(saved):
    plan = saved.seal()
    plan["saved_gJ_digest"] = "other-registered-gradient"
    with pytest.raises(ValueError, match="original reference"):
        worker.load_saved_gradient(plan, saved.rt, saved.actual)


def test_saved_gradient_must_match_actual_reference_too(saved):
    plan = saved.seal()
    saved.actual["gJ"]["weight"][0, 1] += 1
    with pytest.raises(ValueError, match="original reference"):
        worker.load_saved_gradient(plan, saved.rt, saved.actual)


class Monitor:
    def __init__(self, *, fail_at=None):
        self.fail_at = fail_at
        self.labels = []

    def clear_unused(self, label):
        self.labels.append(label)
        if label == self.fail_at:
            raise ValueError("mock unchanged resource gate failed")

    def report(self):
        return dict(
            all_passed=self.fail_at not in self.labels,
            max_observed_peak_allocated_bytes=17,
            min_boundary_free_bytes=23,
            peak_reset_calls=0,
            observations=[{"label": label} for label in self.labels],
        )


@pytest.fixture
def execution(tmp_path):
    model = torch.nn.Linear(2, 1, bias=False)
    gradient = {"weight": torch.tensor([[1.25, -2.5]])}
    prepared = dict(G={"weight": torch.ones(1, 2)}, theta_bar={"weight": torch.ones(1, 2) * 2})
    result = dict(
        a={"weight": torch.ones(1, 2) * 3},
        C={"task": {"c": 1.5}},
        distribution={"pi_next": {"task": {"c": 1.0}}},
    )
    actual = dict(
        gJ=copy.deepcopy(gradient),
        G=copy.deepcopy(prepared["G"]),
        theta_bar=copy.deepcopy(prepared["theta_bar"]),
        point_id="point",
        pullback=copy.deepcopy(result["a"]),
        C=copy.deepcopy(result["C"]),
        q_next=copy.deepcopy(result["distribution"]["pi_next"]),
        mu=0.1,
        pre_state={"pi": {"task": {"c": 1.0}}, "prior": {"task": {"c": 1.0}}},
    )
    calls = []
    class_result = {"original-class": {"weight": torch.ones(1, 2)}}

    def class_pass(_rt, received_model, pool, **kwargs):
        assert received_model is model and pool == "pool"
        assert kwargs["device"] == "cuda:0"  # Mock records the production API, uses no CUDA.
        calls.append("class")
        return class_result, {"saved_live_bytes": 0}

    def prepare(parameters, optimizer, gradients, pi, mu):
        assert gradients is class_result and set(parameters) == {"weight"}
        assert pi == actual["pre_state"]["pi"] and mu == actual["mu"]
        calls.append("prepare")
        return prepared

    def update(received_prepared, gradients, gJ, pi, prior, mu, **kwargs):
        assert received_prepared is prepared and gradients is class_result
        assert gJ is not actual["gJ"] and torch.equal(gJ["weight"], gradient["weight"])
        assert kwargs["contribution_only"] is True and kwargs["control_tasks"] == ["task"]
        calls.append("update")
        return result

    runtime = SimpleNamespace(
        torch=SimpleNamespace(save=torch.save, cuda=SimpleNamespace(synchronize=lambda: None)),
        v8=SimpleNamespace(
            parameter_digest=digest,
            prepare_virtual_point=prepare,
            update_distribution=update,
            PARAMETERS={},
        ),
    )
    optimizer = SimpleNamespace(step=lambda: pytest.fail("real optimizer step prohibited"))
    inherited = SimpleNamespace(state_identity=lambda *_args: digest(model.state_dict()))
    training = SimpleNamespace(
        DEFAULT_ROOT="fixture", checked_launch=lambda *_args: (None, "pool", None, None)
    )
    manifest = tmp_path / "manifest" / "record.json"
    worker.control.publish(manifest, {"point_id": "point"})
    plan = dict(
        id="CPU-mock",
        saved_gJ_digest=digest(gradient),
        benchmark_manifest=worker.control.entry(manifest),
        allocated_memory_limit_bytes=76 * 1024**3,
        free_memory_reserve_bytes=2 * 1024**3,
    )
    guard = SimpleNamespace(
        recompute_point_id=lambda *_a, **_k: "point",
        check_recomputed_point=lambda record, point: record["point_id"] == point,
    )
    monitor, stop = Monitor(), SimpleNamespace(requested=False)
    report = {"complete_replay": True, "replayed_responses_this_supplement": 0}
    kwargs = dict(
        directory=tmp_path / "tail_validation",
        plan=plan,
        actual=actual,
        gradient=gradient,
        feedback_report=report,
        model=model,
        optimizer=optimizer,
        training=training,
        rt=runtime,
        inherited=inherited,
        guard=guard,
        memory=SimpleNamespace(
            class_gradients_with_cpu_saves=class_pass,
            BACKEND_VERSION=worker.control.BACKEND_VERSION,
        ),
        monitor=monitor,
        stop=stop,
        immutable=immutable,
    )
    return SimpleNamespace(
        kwargs=kwargs,
        calls=calls,
        result=result,
        prepared=prepared,
        actual=actual,
        monitor=monitor,
        stop=stop,
        plan=plan,
    )


def test_mock_tail_one_class_pass_no_replay_and_independent_results(execution):
    result = worker.execute_tail(**execution.kwargs)
    assert execution.calls == ["class", "prepare", "update"]
    assert result["status"] == "COMPLETE" and result["numeric_pass"] is True
    assert result["replayed_responses"] == 0 and result["reused_completed_responses"] == 573
    assert result["class_gradient_passes"] == 1
    assert result["tail_supplement_only"] is True
    assert result["original_V33_failure_reclassified"] is False
    assert all(result["comparison"].values())
    assert execution.monitor.labels == [
        "before_class_gradients",
        "class_gradients_complete",
        "virtual_point_complete",
        "after_distribution",
    ]
    assert not torch.cuda.is_initialized()


def test_final_memory_gate_failure_preserves_actual_numeric_payload_and_record(execution):
    execution.monitor.fail_at = "after_distribution"
    with pytest.raises(ValueError, match="resource gate failed"):
        worker.execute_tail(**execution.kwargs)
    directory = execution.kwargs["directory"]
    numeric = worker.control.checked(directory / "numeric_comparison/record.json")
    assert numeric["numeric_pass"] is True and numeric["resource_acceptance_not_implied"] is True
    assert numeric["computed_C"] == execution.result["C"]
    assert numeric["computed_pi"] == execution.result["distribution"]["pi_next"]
    payload = numeric["computed_payload"]
    assert worker.control.sha(payload["path"]) == payload["sha256"]
    tensors = torch.load(payload["path"], map_location="cpu", weights_only=False)
    assert tensors["C"] == execution.result["C"]
    assert tensors["pi"] == execution.result["distribution"]["pi_next"]
    assert torch.equal(tensors["aggregate_G"]["weight"], execution.prepared["G"]["weight"])
    assert torch.equal(tensors["pullback"]["weight"], execution.result["a"]["weight"])
    assert not (directory / "result/record.json").exists()


@pytest.mark.parametrize("changed", ["C", "pi", "pullback", "state"])
def test_failed_numeric_comparison_is_serialized_before_rejection(execution, changed):
    if changed == "C":
        execution.result["C"]["task"]["c"] += 1
    elif changed == "pi":
        execution.result["distribution"]["pi_next"]["task"]["c"] = 0.5
    elif changed == "pullback":
        execution.result["a"]["weight"][0, 0] += 1
    else:
        identities = iter(["before", "after"])
        execution.kwargs["inherited"] = SimpleNamespace(state_identity=lambda *_a: next(identities))
    with pytest.raises(ValueError, match="numerical comparison failed"):
        worker.execute_tail(**execution.kwargs)
    numeric = worker.control.checked(
        execution.kwargs["directory"] / "numeric_comparison/record.json"
    )
    assert numeric["numeric_pass"] is False
    assert numeric["computed_C"] == execution.result["C"]
    assert "after_distribution" not in execution.monitor.labels


@pytest.mark.parametrize("field", ["G", "theta_bar"])
def test_point_mismatch_stops_before_distribution_and_preserves_comparison(execution, field):
    execution.prepared[field]["weight"][0, 0] += 1
    with pytest.raises(ValueError, match="virtual point differs"):
        worker.execute_tail(**execution.kwargs)
    assert execution.calls == ["class", "prepare"]
    directory = execution.kwargs["directory"]
    assert (directory / "point_comparison/record.json").exists()
    assert not (directory / "numeric_comparison/record.json").exists()


def test_stop_after_class_does_not_prepare_or_publish_success(execution):
    execution.stop.requested = True
    with pytest.raises(ValueError, match="stop requested after class"):
        worker.execute_tail(**execution.kwargs)
    assert execution.calls == ["class"]
    assert (execution.kwargs["directory"] / "storage_receipt/record.json").exists()


def test_accepted_resources_maps_raw_observations_without_replacing_limits(execution):
    execution.monitor.labels = ["after_distribution"]
    mapped = worker.accepted_resources(execution.monitor, execution.plan)
    assert mapped == dict(
        all_gates_passed=True,
        limits_unchanged=True,
        peak_resets_before_model_load=1,
        peak_resets_after_model_loading_begins=0,
        helper_peak_reset_calls=0,
        maximum_allocated_bytes=76 * 1024**3,
        minimum_device_free_bytes=2 * 1024**3,
        observed_peak_allocated_bytes=17,
        observed_minimum_boundary_free_bytes=23,
        observations=[{"label": "after_distribution"}],
    )
    execution.monitor.fail_at = "after_distribution"
    assert worker.accepted_resources(execution.monitor, execution.plan)["all_gates_passed"] is False


def test_worker_has_no_replay_sampling_or_optimizer_step_entry_and_one_peak_reset():
    tree = ast.parse(Path(worker.__file__).read_text())
    calls = [node.func for node in ast.walk(tree) if isinstance(node, ast.Call)]
    prohibited = {
        "feedback_gradient",
        "ReplaySession",
        "execute_cohort",
        "execute_micro",
        "collect",
        "collect_feedback",
        "generate",
        "sample",
        "step",
    }
    assert not {node.attr for node in calls if isinstance(node, ast.Attribute)} & prohibited
    assert not {node.id for node in calls if isinstance(node, ast.Name)} & prohibited
    resets = [
        node
        for node in calls
        if isinstance(node, ast.Attribute) and node.attr == "reset_peak_memory_stats"
    ]
    assert len(resets) == 1
    run = next(
        node for node in tree.body if isinstance(node, ast.FunctionDef) and node.name == "run"
    )
    model_load = next(
        node
        for node in ast.walk(run)
        if isinstance(node, ast.Call)
        and isinstance(node.func, ast.Attribute)
        and node.func.attr == "_load_components"
    )
    assert resets[0].lineno < model_load.lineno


def test_mutable_worker_rejected_before_stage_or_dependencies(tmp_path, monkeypatch):
    monkeypatch.setattr(worker.control, "checked_protocol", lambda *_a: {"id": "mock"})
    monkeypatch.setattr(
        worker, "dependencies", lambda: pytest.fail("mutable worker imported runtime")
    )
    with pytest.raises(ValueError, match="committed frozen"):
        worker.run(tmp_path, "tail_validation", 7)
    assert not (tmp_path / "tail_validation").exists()


@pytest.mark.parametrize("stage,gpu", [("cohort_resume", 7), ("tail_validation", 3)])
def test_worker_rejects_unregistered_stage_or_gpu_before_dependencies(
    tmp_path, monkeypatch, stage, gpu
):
    monkeypatch.setattr(worker.control, "checked_protocol", lambda *_a: {"id": "mock"})
    monkeypatch.setattr(
        worker, "__file__", str(tmp_path / "implementation" / Path(worker.__file__).name)
    )
    monkeypatch.setattr(
        worker, "dependencies", lambda: pytest.fail("invalid launch imported runtime")
    )
    with pytest.raises(ValueError, match="unregistered tail stage/GPU"):
        worker.run(tmp_path, stage, gpu)


def test_fresh_dependency_import_does_not_initialize_cuda():
    program = """
import sys
sys.path.insert(0, sys.argv[1])
import finqa_v34_tail_worker as worker
training, rt, inherited, guard, pause, memory, mechanism, immutable = worker.dependencies()
assert not rt.torch.cuda.is_initialized()
assert memory.BACKEND_VERSION == worker.control.BACKEND_VERSION
assert callable(rt.v8.class_gradients)
assert not hasattr(worker, 'execute_cohort')
assert not hasattr(worker, 'feedback_gradient')
"""
    subprocess.run(
        [sys.executable, "-c", program, str(Path(worker.__file__).parent)],
        check=True,
        capture_output=True,
        text=True,
        timeout=60,
        env={**os.environ, "CUDA_VISIBLE_DEVICES": "", "PYTHONDONTWRITEBYTECODE": "1"},
    )
