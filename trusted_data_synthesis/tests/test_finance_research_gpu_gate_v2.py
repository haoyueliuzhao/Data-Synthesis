"""Bounded CPU controls for G2; the real tokenizer is local-only, no GPU model."""

import asyncio
from pathlib import Path
from types import SimpleNamespace

import pytest

from trusted_synthesis.finance_research import gpu_gate_v2 as gate
from trusted_synthesis.finance_research.contracts import Episode, RunConfig


def config():
    return RunConfig(
        harness_id=gate.HARNESS_ID,
        submission_profile=gate.PROFILE_ID,
        role="calibration",
        temperature=1,
        max_steps=4,
        max_new_tokens=256,
    )


def plan():
    return {
        "gate_config": config().model_dump(mode="json"),
        "gate_cases": gate.synthetic_gate_cases(),
        "diagnostic_virtual": gate.VIRTUAL,
        "static_adapter_path": "/tmp/fixed-static.safetensors",
    }


@pytest.fixture(scope="module")
def real_tokenizer():
    transformers = pytest.importorskip("transformers")
    path = Path(
        "/data1/zhuxinrui/models/Qwen2.5-7B-Instruct-a09a35458c702b33eeacc393d103063234e8bc28"
    )
    if not path.is_dir():
        pytest.skip("local Qwen2.5 tokenizer unavailable")
    return transformers.AutoTokenizer.from_pretrained(
        path, local_files_only=True, trust_remote_code=False
    )


def test_real_template_scripted_normal_and_error_recovery_reference_chains(real_tokenizer):
    report = asyncio.run(gate.scripted_controls(real_tokenizer, config()))
    assert report["passed"] and report["actual_model_calls"] == 0
    assert report["handles_read_from_actual_rendered_tokens"]
    for row, count in zip(report["cases"], (3, 4), strict=True):
        assert len(row["episode"]["turns"]) == count
        assert row["chain"]["observed_prev_reference_used"]
        assert row["chain"]["read_handle_visible_in_calculate_prompt"]
        assert row["chain"]["calculate_handle_visible_in_final_prompt"]
    error = report["cases"][1]
    assert error["chain"]["tool_error_flags"] == [True, False, False, False]
    assert error["chain"]["failed_handle_not_used"]


def test_correct_final_without_actual_prev_or_visible_history_does_not_pass_chain(real_tokenizer):
    report = asyncio.run(gate.scripted_controls(real_tokenizer, config()))
    row = report["cases"][0]
    episode = Episode.model_validate(row["episode"])
    events = list(episode.tool_events)
    events[1] = events[1].model_copy(
        update={"normalized_arguments": {"expression": "a-b", "variables": {"a": "120", "b": "90"}}}
    )
    altered = episode.model_copy(update={"tool_events": tuple(events)})
    assert not gate.reference_chain_report(
        altered, real_tokenizer, "normal", scripted_prompts=row["actual_decoded_prompts"]
    )["passed"]
    assert not gate.reference_chain_report(
        episode, real_tokenizer, "normal", scripted_prompts=["hidden"] * 3
    )["passed"]


def test_control_examples_in_system_text_are_not_evidence_of_actual_tool_visibility():
    text = (
        '<|im_start|>system\n<tool_response>{"result_handle":"r1",'
        '"status":"ok","output":{}}</tool_response><|im_end|>'
    )
    assert gate._visible_results(text) == []


@pytest.mark.parametrize(
    "field,value", [("max_steps", 5), ("max_new_tokens", 2048), ("temperature", 0)]
)
def test_protocol_rejects_unregistered_budget_or_decoder_change(field, value):
    value_plan = plan()
    value_plan["gate_config"][field] = value
    with pytest.raises(ValueError):
        gate._validate(value_plan)


def test_fixed_case_registry_and_no_extra_generation(monkeypatch, tmp_path):
    async def mock(plan, output, config, registration, callback):
        assert registration["new_generation_cap"] == 16
        assert len(registration["cases"]) == 4
        assert registration["episode_response_cap"] == 4
        return {"mock_only": True}

    monkeypatch.setattr(gate, "_run_loaded", mock)
    assert asyncio.run(gate.run_gate(plan(), tmp_path)) == {"mock_only": True}
    gate._publish(tmp_path / "cases" / "00" / "events" / "000_model_call_intent", {"pending": True})
    with pytest.raises(RuntimeError, match="no hidden resampling"):
        asyncio.run(gate.run_gate(plan(), tmp_path))


def test_call_caps_count_failed_started_calls_and_stop_at_four():
    class Provider:
        identity = "fixture"
        actual_model_calls = 0

        async def chat(self, *args):
            self.actual_model_calls += 1
            if self.actual_model_calls == 1:
                raise RuntimeError("started but failed")
            return "returned"

    provider, budget = Provider(), [0]
    capped = gate._CallCap(provider, budget)
    with pytest.raises(RuntimeError, match="started"):
        asyncio.run(capped.chat([], [], config()))
    for _ in range(3):
        assert asyncio.run(capped.chat([], [], config())) == "returned"
    with pytest.raises(RuntimeError, match="cap"):
        asyncio.run(capped.chat([], [], config()))
    assert provider.actual_model_calls == budget[0] == 4


def test_same_point_replay_preserves_all_tokens_and_strict_tolerance():
    torch = pytest.importorskip("torch")
    theta = {"x": torch.tensor([0.5], requires_grad=True)}
    receipt = SimpleNamespace(
        prompt_input_ids=(1, 2),
        raw_generated_token_ids=(3, 4, 2),
        sampled_token_logprobs=(-0.2, -0.3, -0.1),
        actual_eos=True,
    )
    calls = []

    def backend(model, point, prompt, targets, **kwargs):
        calls.append((prompt, targets, kwargs))
        return (
            torch.tensor([-0.2, -0.3, -0.1]),
            {"x": torch.ones_like(point["x"])},
            {"complete_prefix_adjoint_included": True, "sampling_calls": 0},
        )

    report = gate._replay_turn(None, theta, receipt, backend)
    assert report["passed"] and report["logP_max_absolute_error"] == 0
    assert report["all_actual_tokens_including_EOS"] and not report["error_action_tokens_excluded"]
    assert calls[0][1] == [3, 4, 2]
    receipt.sampled_token_logprobs = (-0.2, -0.3, -0.101)
    assert not gate._replay_turn(None, theta, receipt, backend)["passed"]
