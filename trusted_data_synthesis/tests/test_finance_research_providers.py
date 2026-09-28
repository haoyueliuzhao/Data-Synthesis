"""CPU mock generation and mocked HTTP only; no Student load/API/CUDA calls."""

import asyncio
import json
from types import SimpleNamespace

import pytest

from trusted_synthesis.finance_research.contracts import (
    ContextLimitError,
    ProviderCallError,
    RunConfig,
)
from trusted_synthesis.finance_research.providers import (
    DeepSeekFlashProvider,
    LocalTorchProvider,
    ScriptedProvider,
    canonical_assistant_message,
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
        self.messages, self.tools = messages, kwargs.get("tools")
        self.template_kwargs = kwargs
        return json.dumps(messages)

    def __call__(self, text, **kwargs):
        assert kwargs == {"add_special_tokens": False, "truncation": False, "padding": False}
        return {"input_ids": [1, 1, 1]}

    def decode(self, ids, **kwargs):
        assert ids == [3]  # EOS is preserved in receipt but not presentation text.
        return '<tool_call>\n{"name":"submit_answer","arguments":{"answer":"3"}}\n</tool_call>'


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
    assert local.tokenizer.messages == [{"role": "user", "content": "q"}]
    assert local.tokenizer.tools == tools
    assert turn.tool_calls[0].arguments == {"answer": "3"}
    canonical = canonical_assistant_message(turn)
    assert canonical["content"] == ""
    assert canonical["tool_calls"][0]["function"]["arguments"] == {"answer": "3"}
    assert turn.raw_text.startswith("<tool_call>")
    assert turn.provider_metadata["tool_protocol"] == "qwen2.5-native-tool-call-v1"
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
    assert turn.provider_metadata["public_request"] == client.requests[0][1]["json"]
    assert client.requests[0][1]["json"]["model"] == "deepseek-flash"
    assert "test-key" not in json.dumps(turn.model_dump())
    with pytest.raises(ValueError, match="deepseek-flash"):
        DeepSeekFlashProvider(api_key="test", model="deepseek-v4-pro")
    with pytest.raises(ValueError, match="cannot supply"):
        asyncio.run(api.chat([], [], feedback_config()))
    assert api.actual_model_calls == 1
    failed = DeepSeekFlashProvider(api_key="test", client=Client(fail=True))
    with pytest.raises(ProviderCallError) as captured:
        asyncio.run(failed.chat([], [], RunConfig()))
    assert captured.value.settlement == "unknown"
    assert captured.value.evidence["service_response_received"] is False
    assert failed.actual_model_calls == 1 and len(failed._client.requests) == 1


def test_api_native_tools_preserve_response_and_map_canonical_history():
    class ToolClient(Client):
        async def post(self, url, **kwargs):
            self.requests.append((url, kwargs))
            self.value = {
                "id": "api-tools",
                "model": "deepseek-flash",
                "choices": [
                    {
                        "finish_reason": "tool_calls",
                        "message": {
                            "content": "I will inspect the table.",
                            "tool_calls": [
                                {
                                    "id": "native-1",
                                    "type": "function",
                                    "function": {
                                        "name": "read_source",
                                        "arguments": '{ "source_id" : "table-1" }',
                                    },
                                }
                            ],
                        },
                    }
                ],
                "usage": {"prompt_tokens": 4, "completion_tokens": 5},
            }
            return SimpleNamespace(raise_for_status=lambda: None, json=lambda: self.value)

    client = ToolClient()
    api = DeepSeekFlashProvider(api_key="fixture", client=client)
    turn = asyncio.run(api.chat([], [], RunConfig()))
    canonical = canonical_assistant_message(turn)
    assert canonical["content"] == turn.raw_text == "I will inspect the table."
    assert canonical["tool_calls"][0]["function"]["arguments"] == {"source_id": "table-1"}
    assert turn.provider_metadata["api_response"] == client.value
    assert turn.tool_calls[0].raw_arguments == '{ "source_id" : "table-1" }'
    asyncio.run(api.chat([canonical], [], RunConfig()))
    argument = client.requests[-1][1]["json"]["messages"][0]["tool_calls"][0]["function"][
        "arguments"
    ]
    assert isinstance(argument, str) and json.loads(argument) == {"source_id": "table-1"}
    assert isinstance(canonical["tool_calls"][0]["function"]["arguments"], dict)


def test_local_rejects_api_string_arguments_before_generation():
    local = provider()
    messages = [
        {
            "role": "assistant",
            "content": "",
            "tool_calls": [
                {
                    "function": {"name": "read_source", "arguments": '{"source_id":"table-1"}'},
                }
            ],
        }
    ]
    with pytest.raises(ValueError, match="object-valued arguments"):
        asyncio.run(local.chat(messages, [], RunConfig()))
    assert local.actual_model_calls == 0


def test_legacy_provider_does_not_inject_native_tools_or_parse_old_loop_output():
    local = provider()
    raw = '{"final":{"answer":"3","scale":"","program":"add(1, 2)"}}'
    local.tokenizer.decode = lambda ids, **kwargs: raw
    messages = [
        {
            "role": "system",
            "content": 'Old JSON grammar: {"tool": ..., "arguments": ...} or {"final": ...}.',
        },
        {"role": "user", "content": "Question"},
    ]
    turn = asyncio.run(
        local.chat(
            messages,
            [{"type": "function", "function": {"name": "must_not_render"}}],
            RunConfig(local_tool_protocol="legacy-json-v1", temperature=0),
        )
    )
    assert "tools" not in local.tokenizer.template_kwargs
    assert local.tokenizer.messages == messages
    assert turn.raw_text == raw and turn.tool_calls == ()
    assert turn.receipt.raw_generated_token_ids == (3, 2)
    assert turn.receipt.actual_eos and turn.receipt.sampled_token_logprobs is None
    assert turn.provider_metadata["tool_protocol"] == "legacy-json-v1"
    assert turn.provider_metadata["request"]["template_tools_kwarg_used"] is False
    assert turn.provider_metadata["request"]["tools"] == []
    assert turn.provider_metadata["tool_schemas_rendered_by"] == "legacy_system_prompt_only"
    assert canonical_assistant_message(turn) == {"role": "assistant", "content": raw}


def test_direct_provider_keeps_raw_submission_and_never_injects_or_executes_tools():
    local = provider()
    raw = '{"answer":"3","scale":"","program":"add(1, 2)"}'
    local.tokenizer.decode = lambda ids, **kwargs: raw
    config = RunConfig(local_tool_protocol="direct-json-v1", temperature=0, max_steps=1)
    messages = [
        {"role": "system", "content": "Submit one strict JSON object."},
        {"role": "user", "content": "Original public task"},
    ]
    turn = asyncio.run(local.chat(messages, [], config))
    assert "tools" not in local.tokenizer.template_kwargs
    assert local.tokenizer.messages == messages
    assert turn.raw_text == raw and turn.tool_calls == ()
    assert turn.receipt.raw_generated_token_ids == (3, 2) and turn.receipt.actual_eos
    assert (
        turn.provider_metadata["tool_schemas_rendered_by"] == "direct_public_submission_prompt_only"
    )
    with pytest.raises(ValueError, match="no tools"):
        asyncio.run(local.chat(messages, [{"type": "function"}], config))
    assert local.actual_model_calls == 1


@pytest.mark.parametrize("bad_arguments", ["{broken", '{"x":1,"x":2}', '{"x":NaN}', "[]", None])
def test_api_fully_accounted_tool_format_error_is_retained_model_failure(bad_arguments):
    function = {"name": "read_source"}
    if bad_arguments is not None:
        function["arguments"] = bad_arguments
    value = {
        "id": "returned-invalid-model-call",
        "model": "deepseek-flash",
        "choices": [
            {
                "finish_reason": "tool_calls",
                "message": {
                    "content": "I will inspect the table.",
                    "tool_calls": [{"id": "call-1", "type": "function", "function": function}],
                },
            }
        ],
        "usage": {"prompt_tokens": 20, "completion_tokens": 10},
    }

    class ReturnedClient(Client):
        async def post(self, url, **kwargs):
            self.requests.append((url, kwargs))
            return SimpleNamespace(
                status_code=200,
                text=json.dumps(value),
                raise_for_status=lambda: None,
                json=lambda: value,
            )

    client = ReturnedClient()
    api = DeepSeekFlashProvider(api_key="fixture", client=client)
    turn = asyncio.run(api.chat([], [], RunConfig()))
    assert turn.tool_calls == () and turn.finish_reason == "tool_calls"
    assert turn.raw_text == "I will inspect the table."
    assert turn.provider_metadata["api_response"] == value
    assert turn.provider_metadata["public_request"] == client.requests[0][1]["json"]
    assert turn.provider_metadata["parse_error"] == "malformed_native_tool_calls_no_repair"
    assert turn.provider_metadata["model_tool_format_failure"] is True
    assert turn.usage == {"prompt_tokens": 20, "completion_tokens": 10}
    assert api.actual_model_calls == 1 and len(client.requests) == 1


def test_model_failure_counted_without_fabricated_turn():
    local = provider()

    def fail(**kwargs):
        raise RuntimeError("mock generation error")

    local.model.generate = fail
    with pytest.raises(ProviderCallError) as captured:
        asyncio.run(local.chat([], [], feedback_config()))
    assert captured.value.settlement == "unknown"
    assert captured.value.actual_model_calls == 1
    assert captured.value.evidence["token_receipt_available"] is False
    assert local.actual_model_calls == 1


@pytest.mark.parametrize(
    "status, value, expected",
    [
        (429, {"error": "rate limited"}, "service_failure"),
        (503, {"error": "temporarily unavailable"}, "service_failure"),
        (200, {"choices": []}, "unknown"),
        (200, {"model": "other-model", "choices": [{"message": {"content": "answer"}}]}, "unknown"),
        (200, {"choices": [{"message": {"tool_calls": [{"function": {"name": "x"}}]}}]}, "unknown"),
    ],
)
def test_api_explicit_service_failure_is_distinct_from_unsettled_response(status, value, expected):
    class ReturnedClient(Client):
        async def post(self, url, **kwargs):
            self.requests.append((url, kwargs))
            return SimpleNamespace(
                status_code=status,
                text=json.dumps(value),
                raise_for_status=lambda: None,
                json=lambda: value,
            )

    client = ReturnedClient()
    api = DeepSeekFlashProvider(api_key="never-record-key", client=client)
    with pytest.raises(ProviderCallError) as captured:
        asyncio.run(api.chat([], [], RunConfig()))
    failure = captured.value
    assert failure.settlement == expected
    assert failure.actual_model_calls == api.actual_model_calls == 1
    assert failure.evidence["raw_service_body"] == json.dumps(value)
    assert failure.evidence["public_request"]["model"] == "deepseek-flash"
    assert failure.evidence["retries"] == 0 and len(client.requests) == 1
    assert "never-record-key" not in json.dumps(failure.evidence)
