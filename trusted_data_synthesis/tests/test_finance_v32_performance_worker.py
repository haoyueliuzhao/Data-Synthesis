"""CPU-only controls for the measurement shell, not CUDA speed evidence."""

import copy
import importlib
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest
import torch
from test_finance_v19_optimized_replay import cpu_baseline, tiny

sys.path.insert(0, str(Path(__file__).parents[1] / "scripts"))
worker = importlib.import_module("finqa_v32_performance_worker")
v8 = importlib.import_module("trusted_synthesis.finance_research.v8_training_driver")
variants = importlib.import_module("finqa_v32_replay_variants")
immutable = importlib.import_module("trusted_synthesis.core.immutable_artifacts")
RT = SimpleNamespace(v8=v8, torch=torch)


def test_restore_real_nonempty_adam_and_rng_not_fresh_optimizer():
    torch.manual_seed(431)
    model = torch.nn.Linear(3, 2)
    model.register_buffer("kept", torch.tensor([2.0]))
    optimizer = torch.optim.AdamW(model.parameters(), lr=1e-4, foreach=False, fused=False)
    model(torch.ones(1, 3)).sum().backward()
    optimizer.step()
    optimizer.zero_grad()
    before = dict(
        parameters={n: p.detach().clone() for n, p in model.named_parameters()},
        buffers={n: p.detach().clone() for n, p in model.named_buffers()},
        optimizer=copy.deepcopy(optimizer.state_dict()),
        rng=v8._rng(),
        model_training=False,
    )
    with torch.no_grad():
        model.weight.add_(4)
        model.kept.add_(7)
    torch.manual_seed(111)
    optimizer.state.clear()
    parameters, identity = worker.restore_pre_state(RT, model, optimizer, before)
    assert len(optimizer.state) == 2
    assert not model.training
    assert identity["optimizer"] == v8._tree_digest(before["optimizer"])
    assert identity["rng"] == v8._tree_digest(before["rng"])
    assert all(torch.equal(parameters[n], value) for n, value in before["parameters"].items())


def test_restore_refuses_missing_parameter_coordinate():
    model = torch.nn.Linear(2, 1)
    optimizer = torch.optim.AdamW(model.parameters())
    before = dict(parameters={}, buffers={}, optimizer={}, rng={}, model_training=False)
    with pytest.raises(ValueError, match="parameter coordinates"):
        worker.restore_pre_state(RT, model, optimizer, before)


def test_equal_logp_does_not_hide_changed_or_missing_gradient():
    values = torch.tensor([1.0, 2.0])
    original = {"a": torch.ones(2), "b": torch.zeros(2)}
    reference = dict(values=values, gradient=original)
    changed = {"a": torch.ones(2), "b": torch.tensor([0.0, 1.0])}
    result = worker.compare_tensors(RT, values, changed, reference)
    assert result["bitwise_logp_equal"] and not result["bitwise_gradient_equal"]
    missing = worker.compare_tensors(RT, values, {"a": original["a"]}, reference)
    assert not missing["shape_dtype_keys_equal"]
    assert not missing["bitwise_gradient_equal"]


def test_case_saved_bytes_are_bound_and_corruption_rejected(tmp_path):
    directory = tmp_path / "micro_R0/cases/case00"
    values, gradient = torch.tensor([1.0]), {"p": torch.tensor([2.0])}
    worker.save_case(directory, {"schema": "CPU_fixture"}, values, gradient, RT, immutable)
    restored = worker.read_case(tmp_path, 0, RT)
    assert torch.equal(restored["values"], values)
    assert torch.equal(restored["gradient"]["p"], gradient["p"])
    with (directory / "result.pt").open("ab") as stream:
        stream.write(b"intentional CPU test corruption")
    with pytest.raises(ValueError, match="R0 case changed"):
        worker.read_case(tmp_path, 0, RT)


def test_profile_ranges_preserve_reference_arithmetic_on_cpu():
    model, theta = tiny()
    prompt, targets = [2, 3, 5, 7], list(range(1, 10))
    baseline, gradients, _ = cpu_baseline()(
        model,
        theta,
        prompt,
        targets,
        block_size=8,
        offload=False,
    )
    before = variants.optimized.legacy.SegmentedOperation.forward
    with torch.profiler.profile(activities=[torch.profiler.ProfilerActivity.CPU]):
        values, actual, accounting = worker.profiled_reference(variants, torch)(
            model,
            theta,
            prompt,
            targets,
            expected=baseline.tolist(),
            block_size=8,
            offload=False,
        )
    assert torch.equal(values, baseline)
    assert all(torch.equal(actual[n], gradients[n]) for n in gradients)
    assert accounting["complete_prefix_adjoint_included"]
    assert variants.optimized.legacy.SegmentedOperation.forward is before


def test_sampled_memory_label_and_no_continuous_peak_claim(monkeypatch):
    sampled = worker.DeviceSamples("cpu-test-no-GPU")

    def query(*_args, **_kwargs):
        sampled.stop.set()
        return "100, 44\n"

    monkeypatch.setattr(worker.subprocess, "check_output", query)
    sampled._run()
    report = sampled.report()
    assert report["sample_count"] == 1
    assert report["sampled_max_device_used_bytes"] == 100 * 1024**2
    assert report["device_peak_is_sampled_not_continuous"] is True
    assert report["sampled_mean_GPU_utilization_percent"] == 44


def test_busy_gpu_rejected_before_attempt_or_cuda_model_load(tmp_path, monkeypatch):
    monkeypatch.setattr(
        worker, "__file__", str(tmp_path / "implementation" / Path(worker.__file__).name)
    )
    monkeypatch.setattr(worker.control, "checked_protocol", lambda _root: {"id": "cpu-fixture"})
    monkeypatch.setattr(worker.control, "inventory", lambda: [{"index": 3}])
    monkeypatch.setattr(worker.control, "eligible", lambda *_args: False)
    fake_rt = SimpleNamespace(
        torch=SimpleNamespace(cuda=SimpleNamespace(is_initialized=lambda: False))
    )
    monkeypatch.setattr(worker, "dependencies", lambda: (None, fake_rt, None, None, None, None))
    with pytest.raises(ValueError, match="not idle"):
        worker.run(tmp_path, "micro_R0", 3)
    assert not (tmp_path / "micro_R0/attempt/record.json").exists()


def test_mutable_worker_cannot_start(tmp_path, monkeypatch):
    monkeypatch.setattr(worker.control, "checked_protocol", lambda _root: {"id": "cpu-fixture"})
    with pytest.raises(ValueError, match="committed frozen"):
        worker.run(tmp_path, "micro_R0", 3)
    assert not (tmp_path / "micro_R0").exists()


def test_cold_resume_requires_real_checkpoint_not_only_pause_summary(tmp_path):
    control = worker.control
    first = dict(
        protocol_id="cpu",
        status="PAUSED_AT_REGISTERED_BOUNDARY",
        pause_cursor=16,
        checkpoint={"cursor": 16},
        replay_report={"restored_completed_responses": 0},
    )
    control.publish(tmp_path / "cohort_first/result/record.json", first)
    with pytest.raises(FileNotFoundError):
        worker.checked_resume_boundary(tmp_path, {"id": "cpu"})


def test_resource_envelope_covers_extra_profile_and_class_pass():
    fake = SimpleNamespace(
        cuda=SimpleNamespace(
            synchronize=lambda: None,
            mem_get_info=lambda: (3 * 1024**3, 80 * 1024**3),
            max_memory_allocated=lambda: 77 * 1024**3,
            max_memory_reserved=lambda: 78 * 1024**3,
        )
    )
    with pytest.raises(ValueError, match="memory envelope"):
        worker.cuda_resources(
            SimpleNamespace(torch=fake),
            dict(
                allocated_memory_limit_bytes=76 * 1024**3,
                free_memory_reserve_bytes=2 * 1024**3,
            ),
        )
