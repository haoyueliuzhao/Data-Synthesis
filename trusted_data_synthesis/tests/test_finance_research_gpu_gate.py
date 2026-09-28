"""CPU-only controls for the four-call gate; never load a GPU model here."""

import asyncio

import pytest

from trusted_synthesis.finance_research import gpu_gate
from trusted_synthesis.finance_research.contracts import PublicTask, RunConfig


def plan():
    task = PublicTask(
        dataset="finqa", task_id="short", question="What is 1+2?", sources=(), version="fixture"
    )
    return {
        "gate_config": RunConfig(
            role="calibration",
            temperature=1.0,
            max_new_tokens=256,
            submission_profile="finqa_program_v1",
        ).model_dump(mode="json"),
        "gate_tasks": {
            "short": task.model_dump(mode="json"),
            "long": task.model_copy(update={"task_id": "long"}).model_dump(mode="json"),
        },
        "diagnostic_virtual": dict(
            lr=1e-5, gradient=1e-4, betas=[0.9, 0.999], eps=1e-8, weight_decay=0.0
        ),
        "static_adapter_path": "/tmp/fixture-adapter.safetensors",
    }


def test_gate_has_exact_four_registered_calls_and_no_scoring(monkeypatch, tmp_path):
    async def no_gpu(plan, output, config, tasks, diagnostic, registration, callback):
        assert config.max_new_tokens == 256
        assert len(registration["cases"]) == registration["new_generation_cap"] == 4
        assert [(case["point"], case["length"]) for case in registration["cases"]] == [
            ("real", "short"),
            ("real", "long"),
            ("virtual", "short"),
            ("virtual", "long"),
        ]
        messages, view = gpu_gate.gate_messages(tasks[0], config)
        assert "list_sources exactly once" in messages[-1]["content"]
        assert view.task_id == tasks[0].task_id and tasks[0].answer_contract == {}
        return {"mock_only": True}

    monkeypatch.setattr(gpu_gate, "_run_loaded", no_gpu)
    assert asyncio.run(gpu_gate.run_gate(plan(), tmp_path)) == {"mock_only": True}


@pytest.mark.parametrize(
    "field, value",
    [("temperature", 0), ("max_new_tokens", 2048), ("local_tool_protocol", "legacy-json-v1")],
)
def test_gate_rejects_changed_sampling_and_budget(field, value):
    value_plan = plan()
    value_plan["gate_config"][field] = value
    with pytest.raises(ValueError):
        gpu_gate._validated(value_plan)


def test_pending_generation_is_never_resampled(tmp_path):
    gpu_gate._publish(tmp_path / "cases" / "00" / "intent", {"registered": True})
    with pytest.raises(RuntimeError, match="no resampling"):
        asyncio.run(gpu_gate.run_gate(plan(), tmp_path))


def test_fifth_case_rejected_before_any_model_load(tmp_path):
    (tmp_path / "cases" / "04").mkdir(parents=True)
    with pytest.raises(ValueError, match="four-call"):
        asyncio.run(gpu_gate.run_gate(plan(), tmp_path))


def test_virtual_install_restores_live_parameter_identity_and_versions():
    torch = pytest.importorskip("torch")
    from torch.nn.utils.stateless import _reparametrize_module

    model = torch.nn.Linear(2, 1)
    actual = dict(model.named_parameters())
    before = {
        name: (id(value), value.data_ptr(), value._version, value.detach().clone())
        for name, value in actual.items()
    }
    virtual = {
        name: (value.detach().clone() + 1e-5).requires_grad_(True) for name, value in actual.items()
    }
    with _reparametrize_module(model, virtual, strict=False):
        assert all(dict(model.named_parameters())[name] is value for name, value in virtual.items())
    for name, value in model.named_parameters():
        original_id, pointer, version, original = before[name]
        assert (id(value), value.data_ptr(), value._version) == (original_id, pointer, version)
        assert torch.equal(value, original)
