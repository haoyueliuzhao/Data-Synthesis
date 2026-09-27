"""CPU mock generation and mocked HTTP only; no Student load/API/CUDA calls."""

import asyncio
import json
from types import SimpleNamespace

import pytest

from trusted_synthesis.finance_research.contracts import ContextLimitError, RunConfig
from trusted_synthesis.finance_research.providers import (
    DeepSeekFlashProvider,
    LocalTorchProvider,
    ScriptedProvider,
    local_model_identity,
    parse_tool_calls,
)

torch = pytest.importorskip("torch")


class Tokenizer:
    special_tokens_map = {"eos_token": "EOS"}
    chat_template = "mock template v1"
    eos_token_id, pad_token_id, bos_token_id = 2, 0, 1

    def get_vocab(self):
        return {"a": 1, "EOS": 2, "answer": 3}

    def apply_chat_template(self, messages, **kwargs):
        self.messages, self.tools = messages, kwargs["tools"]
        return json.dumps(messages)

    def __call__(self, text, **kwargs):
        assert kwargs == {"add_special_tokens": False, "truncation": False, "padding": False}
        return {"input_ids": [1, 1, 1]}

    def decode(self, ids, **kwargs):
        assert ids == [3]  # EOS is preserved in receipt but not presentation text.
        return '{"name":"submit_answer","arguments":{"answer":"3"}}'


class Model(torch.nn.Module):
    def __init__(self):
        super().__init__()
        self.weight = torch.nn.Parameter(torch.tensor([0.25]))
        self.generation_config = SimpleNamespace(eos_token_id=2)
        self.calls = 0

    def generate(self, *, input_ids, attention_mask, generation_config, logits_to_keep):
        self.calls += 1
        torch.rand(1)  # Assert real RNG consumption is captured but isolated.
        self.options = generation_config
        return SimpleNamespace(
            sequences=torch.cat([input_ids, torch.tensor([[3, 2]])], dim=1),
            scores=(torch.tensor([[0.0, 1.0, 2.0, 3.0]]), torch.tensor([[0.0, 1.0, 3.0, 2.0]])),
        )


def provider():
    model, tokenizer = Model(), Tokenizer()
    identity = local_model_identity(model, tokenizer, model_id="tiny-mock", point_id="point-1")
    return LocalTorchProvider(model, tokenizer, identity)


def feedback_config(**changes):
    return RunConfig(tier="VTDO_FEEDBACK", role="feedback", max_new_tokens=8, **changes)


def test_local_preserves_tokens_scores_tools_rng_and_modes():
    local = provider()
    before = torch.get_rng_state().clone()
    tools = [{"type": "function", "function": {"name": "submit_answer"}}]
    turn = asyncio.run(local.chat([{"role": "user", "content": "q"}], tools, feedback_config()))
    assert local.actual_model_calls == local.model.calls == 1
    assert torch.equal(before, torch.get_rng_state()) and local.model.training
    assert turn.receipt.prompt_input_ids == (1, 1, 1)
    assert turn.receipt.raw_generated_token_ids == (3, 2)
    assert len(turn.receipt.sampled_token_logprobs) == 2
    assert turn.receipt.actual_eos and turn.finish_reason == "stop"
    assert turn.receipt.rng_before_sha256 != turn.receipt.rng_after_sha256
    assert "submit_answer" in local.tokenizer.messages[0]["content"]
    assert turn.tool_calls[0].arguments == {"answer": "3"}
    assert local.model.options.temperature == 1.0 and local.model.options.top_k == 0


def test_local_context_rejection_is_not_a_generation_or_truncation():
    local = provider()
    with pytest.raises(ContextLimitError):
        asyncio.run(local.chat([], [], feedback_config(context_limit=9)))
    assert local.actual_model_calls == local.model.calls == 0


@pytest.mark.parametrize("changes", [{"temperature": 0}, {"top_p": 0.9}, {"top_k": 2}])
def test_feedback_rejects_modified_sampling(changes):
    local = provider()
    with pytest.raises(ValueError, match="unmodified"):
        asyncio.run(local.chat([], [], feedback_config(**changes)))
    assert local.actual_model_calls == 0


def test_wrong_identity_and_mutated_parameter_are_rejected():
    local = provider()
    bad = local.identity.model_copy(update={"parameter_digest": "wrong"})
    with pytest.raises(ValueError, match="parameter bytes"):
        LocalTorchProvider(local.model, local.tokenizer, bad)
    with torch.no_grad():
        local.model.weight.add_(1)
    with pytest.raises(ValueError, match="point changed"):
        asyncio.run(local.chat([], [], feedback_config()))


def test_external_virtual_tensors_cannot_fake_the_live_generation_point():
    local = provider()
    with pytest.raises(ValueError, match="not installed"):
        LocalTorchProvider(
            local.model,
            local.tokenizer,
            local.identity,
            parameter_tensors={"weight": local.model.weight.detach().clone()},
        )


def test_scripted_is_fixture_and_never_feedback():
    scripted = ScriptedProvider(['{"name":"answer","arguments":{}}'])
    turn = asyncio.run(scripted.chat([], [], RunConfig()))
    assert turn.provider_metadata["fixture"] and turn.receipt is None
    assert scripted.actual_model_calls == 0
    with pytest.raises(ValueError, match="cannot supply"):
        asyncio.run(scripted.chat([], [], feedback_config()))


def test_strict_tool_json_no_repair():
    assert not parse_tool_calls('```json\n{"name":"x","arguments":{}}\n```', call_prefix="x")
    assert not parse_tool_calls('{"name":"x","arguments":"{broken"}', call_prefix="x")
    assert not parse_tool_calls('{"name":"x","arguments":{"a":1,"a":2}}', call_prefix="x")
    assert not parse_tool_calls('{"name":"x","arguments":{"a":NaN}}', call_prefix="x")
    assert not parse_tool_calls('{"name":"x","arguments":{"a":1e400}}', call_prefix="x")
    arguments = '{ "b": 2, "a" : 1 }'
    raw = '{"name":"x","arguments":' + arguments + "}"
    assert parse_tool_calls(raw, call_prefix="x")[0].raw_arguments == arguments


def test_resume_and_request_order_do_not_change_sampling_identity():
    first, resumed = provider(), provider()
    config = feedback_config()
    target = [{"role": "user", "content": "target"}]
    asyncio.run(first.chat([{"role": "user", "content": "unrelated"}], [], config))
    a = asyncio.run(first.chat(target, [], config))
    b = asyncio.run(resumed.chat(target, [], config))
    assert a.receipt == b.receipt


class Client:
    def __init__(self, fail=False):
        self.requests, self.fail = [], fail

    async def post(self, url, **kwargs):
        self.requests.append((url, kwargs))
        if self.fail:
            raise RuntimeError("mock transport failure")
        return SimpleNamespace(
            raise_for_status=lambda: None,
            json=lambda: {
                "id": "api-one",
                "model": "deepseek-flash",
                "choices": [
                    {
                        "finish_reason": "stop",
                        "message": {"content": "3"},
                    }
                ],
                "usage": {"prompt_tokens": 2, "completion_tokens": 1},
            },
        )


def test_api_flash_only_no_receipt_or_retry():
    client = Client()
    api = DeepSeekFlashProvider(api_key="test-key", client=client)
    turn = asyncio.run(api.chat([], [], RunConfig()))
    assert api.actual_model_calls == 1 and turn.receipt is None
    assert turn.provider_metadata["context_limit_locally_verified"] is False
    assert turn.provider_metadata["API_and_local_token_budget_equivalence_claimed"] is False
    assert client.requests[0][1]["json"]["model"] == "deepseek-flash"
    assert "test-key" not in json.dumps(turn.model_dump())
    with pytest.raises(ValueError, match="deepseek-flash"):
        DeepSeekFlashProvider(api_key="test", model="deepseek-v4-pro")
    with pytest.raises(ValueError, match="cannot supply"):
        asyncio.run(api.chat([], [], feedback_config()))
    assert api.actual_model_calls == 1
    failed = DeepSeekFlashProvider(api_key="test", client=Client(fail=True))
    with pytest.raises(RuntimeError):
        asyncio.run(failed.chat([], [], RunConfig()))
    assert failed.actual_model_calls == 1 and len(failed._client.requests) == 1


def test_model_failure_counted_without_fabricated_turn():
    local = provider()

    def fail(**kwargs):
        raise RuntimeError("mock generation error")

    local.model.generate = fail
    with pytest.raises(RuntimeError):
        asyncio.run(local.chat([], [], feedback_config()))
    assert local.actual_model_calls == 1
