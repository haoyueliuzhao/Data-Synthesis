"""CPU-only tests of real consumer shells and their scoped resource adapters."""

import copy
import importlib
import importlib.util
import json
import signal
import sys
import time
from pathlib import Path
from types import SimpleNamespace

import pytest

sys.path.insert(0, str(Path(__file__).parents[1] / "scripts"))
worker = importlib.import_module("finqa_v42_worker")
endpoint = importlib.import_module("finqa_v42_evaluation")


def require(value, message):
    if not value:
        raise ValueError(message)


def load_cpu_fixture(name):
    spec = importlib.util.spec_from_file_location(
        f"v42_reused_{name}_mock_fixture", Path(__file__).with_name(f"test_finance_v40_{name}.py")
    )
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def seal_paths(monkeypatch, root, modules):
    for module in modules:
        monkeypatch.setattr(
            module, "__file__", str(root / "implementation" / Path(module.__file__).name)
        )


@pytest.fixture
def episode(tmp_path, monkeypatch):
    # Reuse the old CPU-only driver/math fixture but execute the new isolated
    # wrapper. No production controller, actual runtime or CUDA is constructed.
    helper = load_cpu_fixture("worker")
    helper.worker = worker.original
    f = helper.episode.__wrapped__(tmp_path, monkeypatch)
    control = worker.original.control
    monkeypatch.setattr(control, "__file__", str(f.root / "implementation/finqa_v42_controller.py"))
    monkeypatch.setattr(worker, "_controller", lambda: control)
    scope = dict(allowed_gpu_indices=f.plan["allowed_gpu_indices"], gpu_uuids=f.plan["gpu_uuids"])
    f.plan["gpu_admission_policy"] = worker.policy.policy_record(
        scope=scope, evidence_refs=[{"CPU": True}]
    )
    for name in ("resolve_origin_context", "stage_directory", "require_upstream"):
        monkeypatch.setattr(worker.inheritance, name, getattr(worker.original.inheritance, name))
    monkeypatch.setattr(worker.inheritance, "task_cache_overlay_binding", lambda *_args: None)
    monkeypatch.setattr(worker.inheritance, "feedback_resume_binding", lambda *_args: None)
    monkeypatch.setattr(worker.inheritance, "inherited_context", lambda *_args: None)
    old_admit = worker.original.admission.wait_for_pre_cuda_admission
    old_samples = f.bundle.inherited.DeviceSamples

    def samples(uuid):
        assert uuid == f.plan["gpu_uuids"]["4"]
        return old_samples("GPU-fixed")

    monkeypatch.setattr(f.bundle.inherited, "DeviceSamples", samples)

    def admit(*args, context, **kwargs):
        assert context is f.context and not f.cuda.initialized
        result = old_admit(*args, **kwargs)
        return dict(
            result, uuid=f.plan["gpu_uuids"]["4"], free_mib=24 * 1024, processes=[dict(pid=42)]
        )

    monkeypatch.setattr(worker.admission, "wait_for_pre_cuda_admission", admit)
    seal_paths(
        monkeypatch,
        f.root,
        (
            worker,
            worker.original,
            worker.admission,
            worker.inheritance,
            worker.policy,
            worker.task_overlay,
            worker.feedback_resume,
        ),
    )
    f.run = lambda stage: worker.run(f.root, f.directory, stage, 4, time.time() + 3600)
    return f


def test_actual_distribution_shell_keeps_point_feedback_math_and_runtime_gates(episode):
    f = episode
    before = copy.deepcopy(f.context)
    result = f.run("distribution")
    assert result["schema"] == "v42_stage_result.v1"
    assert result["context_id"] == f.context["id"] and f.context == before
    assert result["gpu_uuid"] == f.plan["gpu_uuids"]["4"]
    assert result["minimum_free_mib"] == 24 * 1024 and result["memory_phase"] == "distribution"
    assert result["accepted_V40_pilot_repeated"] is False
    assert result["original_mathematical_functions_unchanged"] is True
    assert result["resources"]["maximum_allocated_bytes"] == 76 * 1024**3
    assert result["resources"]["minimum_device_free_bytes"] == 2 * 1024**3
    assert result["resources"]["peak_resets_after_model_loading_begins"] == 0
    assert result["optimizer_steps"] == result["replayed_responses"] == result["API_calls"] == 0
    assert result["model_optimizer_rng_buffers_unchanged"] is True
    assert f.marker.read_bytes() == f.original_bytes
    assert f.cuda.resets == 1


def test_shared_stage_attempt_still_cannot_be_dispatched_twice(episode):
    f = episode
    f.run("distribution")
    f.cuda.initialized = False
    with pytest.raises(ValueError, match="no automatic retry"):
        f.run("distribution")
    assert f.cuda.resets == 1


def test_actual_training_uses_original_stop_boundary_without_v40_pilot_relabel(episode):
    f = episode
    # CPU fixture keeps one optimizer step for speed; it is the *original*
    # context's boundary here, not a V41 execution-only replacement context.
    f.context["training_stop_step"] = 299
    before = copy.deepcopy(f.context)
    f.run("distribution")
    f.cuda.initialized = False
    result = f.run("train")
    assert result["initial_step"] == 298 and result["committed_step"] == 299
    assert result["actual_optimizer_steps"] == 1 and result["outer_committed"] is True
    assert result["outer_done"] == [298] and f.drivers[-1].steps == 1
    assert result["context_id"] == f.context["id"] and f.context == before
    assert result["memory_phase"] == "train" and result["minimum_free_mib"] == 32 * 1024
    assert "execution_boundary_policy_protocol_id" not in result
    assert "registered_training_stop_step" not in result
    assert result["accepted_V40_pilot_repeated"] is False


def test_v41_wrapper_preserves_context_identity_and_never_restarts_pilot_prefix():
    previous = {
        key: getattr(worker.original, key)
        for key in ("control", "admission", "inheritance", "task_overlay", "execution_context")
    }
    control = SimpleNamespace(require=require, publish=lambda path, body: body)
    context = dict(id="actual", seed=389, arm="Full", step=298, training_stop_step=596)
    with worker.bound_execution(control):
        assert worker.original.execution_context(context, {}) is context
        assert worker.original.inheritance.replay_resume_binding("unused", {}) is None
        assert worker.original.task_overlay.allows_new_shard({}, "shard02") is False
    assert all(getattr(worker.original, key) is value for key, value in previous.items())


def test_virtual_resume_hook_skips_unused_assembly_only_for_registered_point(monkeypatch):
    calls = []
    control = SimpleNamespace(require=require, publish=lambda path, body: body)
    target, other = dict(id="bound"), dict(id="other")
    cache = SimpleNamespace(
        assemble=lambda device="cpu": calls.append("assemble") or "G",
        verification_summary=lambda: dict(strict_payload_file_reads=0),
    )
    monkeypatch.setattr(worker.task_overlay, "build_overlay", lambda *a, **k: cache)
    def original_virtual(*a, **k):
        calls.append("original_virtual")
        return "original"

    def original_feedback(*a, **k):
        calls.append("original_feedback")
        return "original_cohort"
    monkeypatch.setattr(worker.original.base, "execute_virtual", original_virtual)
    monkeypatch.setattr(worker.original.base, "load_feedback", original_feedback)
    monkeypatch.setattr(
        worker.feedback_resume,
        "execute_virtual",
        lambda *a, **k: calls.append("resume_virtual") or "resumed",
    )
    monkeypatch.setattr(
        worker.feedback_resume,
        "load_feedback",
        lambda *a, **k: calls.append("resume_feedback") or "resumed_cohort",
    )
    with worker.bound_execution(control, feedback_binding=dict(original_context_id="bound")):
        view = worker.original.task_overlay.build_overlay(
            None, target, None, "virtual_point", None, None, control=control
        )
        assert view.assemble() is None
        assert view.verification_summary() == dict(strict_payload_file_reads=0)
        ordinary = worker.original.task_overlay.build_overlay(
            None, other, None, "virtual_point", None, None, control=control
        )
        assert ordinary.assemble() == "G"
        assert worker.original.base.execute_virtual(None, target) == "resumed"
        assert worker.original.base.execute_virtual(None, other) == "original"
        assert worker.original.base.load_feedback({}, target, None) == "resumed_cohort"
        assert worker.original.base.load_feedback({}, other, None) == "original_cohort"
    assert worker.original.base.execute_virtual is original_virtual
    assert worker.original.base.load_feedback is original_feedback
    assert calls == [
        "assemble",
        "resume_virtual",
        "original_virtual",
        "resume_feedback",
        "original_feedback",
    ]


@pytest.fixture
def generation(tmp_path, monkeypatch):
    helper = load_cpu_fixture("evaluation")
    helper.subject = endpoint.original
    f = helper.endpoint.__wrapped__(tmp_path, monkeypatch)
    monkeypatch.setattr(
        f.control, "__file__", str(f.root / "implementation/finqa_v42_controller.py")
    )
    monkeypatch.setattr(endpoint, "_controller", lambda: f.control)
    scope = dict(allowed_gpu_indices=f.plan["allowed_gpu_indices"], gpu_uuids=f.plan["gpu_uuids"])
    f.plan["gpu_admission_policy"] = endpoint.policy.policy_record(
        scope=scope, evidence_refs=[{"CPU": True}]
    )
    # Both old generator gates still consume this *real* shared inventory row.
    # It is never converted to an empty-process view of the scientific plan.
    f.source_row.update(free_mib=48 * 1024, processes=[dict(pid=42)])
    f.control.inventory = lambda: [f.source_row]
    seal_paths(
        monkeypatch, f.root, (endpoint, endpoint.original, endpoint.admission, endpoint.policy)
    )
    return f


def test_original_endpoint_generation_math_runs_on_shared_48gib_with_same_science(generation):
    f = generation
    result = endpoint.run(f.root, 389, "c_only", 6, time.time() + 3600)
    assert (
        result["status"] == "COMPLETE" and result["schema"] == "v42_endpoint_generation_result.v1"
    )
    assert result["protocol_id"] == f.plan["id"] and result["context_id"] == "evaluation:389:c_only"
    assert result["minimum_free_mib"] == 48 * 1024 and result["memory_phase"] == "generate"
    assert result["scoring_calls"] == result["API_calls"] == 0
    assert result["resources"]["maximum_allocated_bytes"] == 76 * 1024**3
    assert result["resources"]["minimum_device_free_bytes"] == 2 * 1024**3
    assert result["resources"]["host"]["rss_limit_bytes"] == 192 * 1024**3
    assert result["resources"]["host"]["available_reserve_bytes"] == 96 * 1024**3
    assert f.state.resets == 1 and f.science == f.before
    assert len([call for call in f.calls if call[0] == "original_generate"]) == 1
    assert not [call for call in f.calls if call[0] == "original_eligible"]
    assert (
        f.final.eligible_gpu is f.original_eligible
        and f.final.load_final_provider is f.original_loader
    )
    assert f.source_row["processes"] == [dict(pid=42)]
    records = list(f.root.glob("evaluations/seed389_c_only/generate/**/pre_cuda_wait/status.json"))
    assert len(records) == 3


def test_already_sealed_endpoint_is_not_regenerated(generation):
    f = generation
    f.publish(f.seal_path, {"sealed": True})
    with pytest.raises(ValueError, match="completed model"):
        endpoint.run(f.root, 389, "c_only", 6, time.time() + 3600)
    assert not f.calls and not f.state.cuda


@pytest.fixture
def gpu_gate(tmp_path):
    scope = dict(
        allowed_gpu_indices=list(endpoint.admission.ALLOWED_GPUS),
        gpu_uuids=dict(endpoint.admission.GPU_UUIDS),
    )
    protocol = dict(
        id="CPU_POLICY",
        **scope,
        gpu_admission_policy=endpoint.policy.policy_record(
            scope=scope, evidence_refs=[{"CPU": True}]
        ),
    )
    row = dict(
        index=7,
        uuid=scope["gpu_uuids"]["7"],
        free_mib=48 * 1024,
        processes=[dict(pid=42, gpu_uuid=scope["gpu_uuids"]["7"])],
    )
    state = SimpleNamespace(cuda=False, stopped=False, calls=0)

    def inventory():
        state.calls += 1
        return [row]

    control = SimpleNamespace(
        require=require,
        inventory=inventory,
        host_memory=lambda: dict(available_bytes=256 * 1024**3),
        process_memory=lambda _pid: dict(rss_bytes=1, peak_rss_bytes=1),
        birth=lambda _pid: "CPU_BIRTH",
    )

    def old_gate(*_args):
        pytest.fail("old empty/72GiB gate must not run")

    final = SimpleNamespace(
        torch=SimpleNamespace(cuda=SimpleNamespace(is_initialized=lambda: state.cuda)),
        eligible_gpu=old_gate,
    )
    stop = SimpleNamespace(requested=False)
    science = dict(
        device_policy=dict(allowed_gpu_indices=[3, 4, 5, 7], minimum_free_mib=72 * 1024),
        sampling={"original": True},
        id="ORIGINAL_SCIENCE",
    )

    def enter():
        return endpoint.endpoint_gpu_policy(
            final,
            protocol,
            7,
            control,
            stop,
            time.time() + 100,
            directory=tmp_path,
            context_id="evaluation:389:full",
            extra_stop_requested=lambda: state.stopped,
        )

    return SimpleNamespace(**locals())


def test_endpoint_both_predicates_use_real_shared_row_and_fresh_inventory(gpu_gate):
    f = gpu_gate
    before = copy.deepcopy(f.science)
    with f.enter():
        assert f.final.eligible_gpu(f.science, 7, []) is f.row
        assert f.final.eligible_gpu(f.science, 7, [dict(uuid="stale")]) is f.row
    assert f.state.calls == 2 and f.science == before
    assert f.row["processes"] == [dict(pid=42, gpu_uuid=f.protocol["gpu_uuids"]["7"])]
    assert f.final.eligible_gpu is f.old_gate
    records = list(f.tmp_path.glob("pre_cuda_rechecks/*/pre_cuda_wait/status.json"))
    assert len(records) == 2
    assert all(json.loads(path.read_text())["minimum_free_mib"] == 48 * 1024 for path in records)


@pytest.mark.parametrize(
    "failure", ["uuid", "cuda", "outer_stop", "inner_stop", "rss", "unknown_pid"]
)
def test_endpoint_recheck_still_rejects_nonmemory_safety_failures(gpu_gate, failure):
    f = gpu_gate
    if failure == "uuid":
        f.row["uuid"] = "GPU-OTHER"
    elif failure == "cuda":
        f.state.cuda = True
    elif failure == "outer_stop":
        f.stop.requested = True
    elif failure == "inner_stop":
        f.state.stopped = True
    elif failure == "rss":
        f.control.process_memory = lambda _pid: dict(
            rss_bytes=193 * 1024**3, peak_rss_bytes=193 * 1024**3
        )
    else:
        f.row["processes"] = [dict(pid=None)]
    with pytest.raises((ValueError, endpoint.admission.AdmissionStopped)):
        with f.enter():
            f.final.eligible_gpu(f.science, 7, [])
    assert f.final.eligible_gpu is f.old_gate


def test_endpoint_does_not_accept_changed_device_or_extra_recheck(gpu_gate):
    f = gpu_gate
    with f.enter():
        with pytest.raises(ValueError, match="physical GPU"):
            f.final.eligible_gpu(f.science, 6, [])
        f.final.eligible_gpu(f.science, 7, [])
        f.final.eligible_gpu(f.science, 7, [])
        with pytest.raises(ValueError, match="extra original"):
            f.final.eligible_gpu(f.science, 7, [])


def test_scoring_delegates_without_any_device_policy_scope(monkeypatch, tmp_path):
    sentinel = object()
    calls = []
    control = SimpleNamespace(require=require)
    monkeypatch.setattr(endpoint, "_checked_entry", lambda *_args: None)
    monkeypatch.setattr(endpoint, "_controller", lambda: control)

    def score(root):
        calls.append((root, endpoint.original._controller().original))
        return sentinel

    monkeypatch.setattr(endpoint.original, "score", score)
    assert endpoint.score(tmp_path) is sentinel
    assert calls == [(tmp_path, control)]


def test_legal_inner_endpoint_signal_remains_visible_to_pre_cuda_recheck(monkeypatch, tmp_path):
    monkeypatch.setattr(endpoint, "_checked_entry", lambda *_args: None)
    monkeypatch.setattr(endpoint, "_controller", lambda: SimpleNamespace(require=require))
    observations = []
    original_bound = endpoint.bound_execution

    def capture_binding(control, **kwargs):
        observations.append(kwargs["extra_stop_requested"])
        return original_bound(control, **kwargs)

    def run(*_args):
        received = []
        signal.signal(signal.SIGTERM, lambda number, frame: received.append(number))
        signal.getsignal(signal.SIGTERM)(signal.SIGTERM, None)
        assert received == [signal.SIGTERM]
        assert observations[0]() is True
        return "legal-stop"

    previous = signal.getsignal(signal.SIGTERM)
    monkeypatch.setattr(endpoint, "bound_execution", capture_binding)
    monkeypatch.setattr(endpoint.original, "run", run)
    assert endpoint.run(tmp_path, 389, "full", 7, time.time() + 100) == "legal-stop"
    assert signal.getsignal(signal.SIGTERM) is previous
