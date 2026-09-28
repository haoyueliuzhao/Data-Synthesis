"""Future structured output contract: mocked HTTP and real tokenizer, no model/API/GPU.

The public content counterexample remains in its actual subsequent request.
No fixture asserts that a financial qualification or training gate has passed.
"""

import asyncio
import copy
import hashlib
import json
from types import SimpleNamespace

import pytest
from test_finance_research_r2 import TOKENIZER, visible_envelopes

from trusted_synthesis.finance_research.contracts import (
    ModelIdentity,
    ModelTurn,
    PublicSource,
    PublicTask,
    RunConfig,
    digest,
)
from trusted_synthesis.finance_research.harness import (
    HARNESS_ID,
    STRUCTURED_HARNESS_ID,
    STRUCTURED_PROFILE_ID,
    SYSTEM_PROMPT,
    SYSTEM_PROMPT_V3,
    episode_tool_specs,
    run_episode,
    system_message,
)
from trusted_synthesis.finance_research.profiles import profile_definition, public_run_view
from trusted_synthesis.finance_research.providers import (
    DeepSeekFlashProvider,
    canonical_assistant_message,
    validate_structured_context,
)
from trusted_synthesis.finance_research.qwen_protocol import (
    QWEN_TOOL_PROTOCOL,
    parse_qwen_native_response,
)
from trusted_synthesis.finance_research.tools import VISIBLE_REFERENCE_PROTOCOL, PublicToolSession


def config(**changes):
    return RunConfig(
        harness_id=STRUCTURED_HARNESS_ID,
        submission_profile=STRUCTURED_PROFILE_ID,
        role="sft",
        **changes,
    )


@pytest.fixture
def task():
    return PublicTask(
        dataset="finqa",
        task_id="structured-public-fixture",
        version="synthetic",
        question="What is current revenue minus prior revenue?",
        sources=(
            PublicSource(
                source_id="table:0",
                kind="table",
                locator="table",
                content=[["metric", "current", "prior"], ["Revenue", "10", "2"]],
            ),
        ),
    )


def next_action(observed):
    if not observed:
        return "read_source", {"source_id": "table:0"}
    handle = observed[-1]["result_handle"]
    if "content" in observed[-1]["output"]:
        return "calculate", {
            "expression": "a-b",
            "variables": {
                "a": f"prev:{handle}.output.content.1.1",
                "b": f"prev:{handle}.output.content.1.2",
            },
        }
    return "final_answer", {"answer": f"prev:{handle}.output.result", "program": "subtract(10, 2)"}


class MockClient:
    def __init__(self, *, first_content=None, mode="chain"):
        self.requests, self.first_content, self.mode = [], first_content, mode

    async def post(self, url, **kwargs):
        body = copy.deepcopy(kwargs["json"])
        self.requests.append(body)
        index = len(self.requests) - 1
        observed = [
            json.loads(message["content"])
            for message in body["messages"]
            if message["role"] == "tool"
        ]
        name, arguments = next_action(observed)
        calls = [
            {
                "id": f"mock-tool-{index}",
                "type": "function",
                "function": {"name": name, "arguments": json.dumps(arguments)},
            }
        ]
        content = self.first_content if index == 0 else None
        if self.mode == "multiple":
            calls += [
                {
                    "id": "second-call",
                    "type": "function",
                    "function": {"name": "list_sources", "arguments": "{}"},
                }
            ]
        elif self.mode == "none":
            calls = []
            content = '{"name":"final_answer","arguments":{"answer":"8"}}'
        response = {
            "id": f"mock-response-{index}",
            "model": "deepseek-flash",
            "choices": [
                {
                    "finish_reason": "tool_calls" if calls else "stop",
                    "message": {"role": "assistant", "content": content, "tool_calls": calls},
                }
            ],
            "usage": {"prompt_tokens": 10, "completion_tokens": 10, "total_tokens": 20},
        }
        return SimpleNamespace(
            status_code=200, raise_for_status=lambda: None, json=lambda: response
        )


@pytest.mark.parametrize("content", [None, ""])
def test_empty_API_content_actual_request_tool_replay_round_trip(task, content):
    client = MockClient(first_content=content)
    provider = DeepSeekFlashProvider(api_key="mock-not-a-real-key", client=client)
    cfg = config()
    scope = {"run_id": "structured-control", "episode_id": "empty-content", "attempt": 1}
    result = asyncio.run(run_episode(task, provider, cfg, invocation_context=scope))
    assert result.final_answer == "8" and result.final_program == "subtract(10, 2)"
    assert (
        result.actual_model_calls == len(client.requests) == 3 and result.all_provider_calls_settled
    )
    expected_task = public_run_view(task, STRUCTURED_PROFILE_ID)
    assert client.requests[0]["messages"][0] == system_message(cfg)
    assert json.loads(client.requests[0]["messages"][1]["content"]) == expected_task.model_dump(
        mode="json"
    )
    assert client.requests[0]["tools"] == episode_tool_specs(cfg)
    assert expected_task.sources == task.sources and expected_task.question == task.question
    assert "PRIVATE_GOLD_PROGRAM" not in json.dumps(client.requests)
    replay = PublicToolSession(
        expected_task, reference_protocol=VISIBLE_REFERENCE_PROTOCOL, invocation_context=scope
    )
    for turn, event, actual_request in zip(
        result.turns, result.tool_events, client.requests, strict=True
    ):
        assert turn.provider_metadata["public_request"] == actual_request
        assert turn.provider_metadata["request_sha256"] == digest(actual_request)
        assert canonical_assistant_message(turn)["content"] == ""
        assert turn.receipt is None  # API samples never gain a fabricated local token receipt.
        assert replay.execute(turn.tool_calls[0], invocation_id=event.invocation_id) == event
    assert (
        result.turns[0].provider_metadata["api_response"]["choices"][0]["message"]["content"]
        is content
    )


def test_nonempty_API_content_is_not_deleted_repaired_or_resampled(task):
    prose = "I will read the source and then calculate the difference."
    client = MockClient(first_content=prose)
    provider = DeepSeekFlashProvider(api_key="mock", client=client)
    result = asyncio.run(
        run_episode(
            task,
            provider,
            config(),
            invocation_context={
                "run_id": "structured-control",
                "episode_id": "nonconforming-prose",
                "attempt": 1,
            },
        )
    )
    assert result.final_answer == "8" and len(client.requests) == 3
    assert result.turns[0].raw_text == prose
    assert result.messages[2]["content"] == prose
    assert client.requests[1]["messages"][2]["content"] == prose
    assert result.turns[1].provider_metadata["public_request"]["messages"][2]["content"] == prose
    assert (
        result.turns[0].provider_metadata["api_response"]["choices"][0]["message"]["content"]
        == prose
    )


@pytest.mark.parametrize(
    "mode, stop", [("multiple", "multiple_tool_calls"), ("none", "no_tool_call")]
)
def test_multiple_or_non_native_call_is_normal_retained_model_termination(task, mode, stop):
    client = MockClient(mode=mode)
    provider = DeepSeekFlashProvider(api_key="mock", client=client)
    result = asyncio.run(run_episode(task, provider, config()))
    assert result.stop_reason == stop and result.all_provider_calls_settled
    assert len(client.requests) == len(result.turns) == 1 and result.tool_events == ()
    assert result.final_answer is None
    if mode == "none":
        assert result.turns[0].raw_text.startswith('{"name":')  # Not converted into native calls.


def test_version_pair_and_new_actual_context_cannot_be_silently_used_by_old_identity(task):
    new = config()
    old = RunConfig(harness_id=HARNESS_ID, submission_profile="finqa_program_v2")
    messages = [system_message(new), {"role": "user", "content": "public fixture"}]
    with pytest.raises(ValueError, match="old experiment identity"):
        validate_structured_context(messages, episode_tool_specs(new), old)
    with pytest.raises(ValueError, match="requires finqa_program_v3_structured"):
        system_message(new.model_copy(update={"submission_profile": "finqa_program_v2"}))
    with pytest.raises(ValueError, match="explicit v4"):
        system_message(old.model_copy(update={"submission_profile": STRUCTURED_PROFILE_ID}))
    client = MockClient()
    provider = DeepSeekFlashProvider(api_key="mock", client=client)
    with pytest.raises(ValueError, match="bound system/tool context"):
        asyncio.run(provider.chat([system_message(old)], episode_tool_specs(new), new))
    assert not client.requests and provider.actual_model_calls == 0


def test_old_profile_and_SYSTEM_bytes_and_financial_schemas_remain_unchanged():
    assert (
        digest(profile_definition("finqa_program_v1"))
        == "618ffb0137c6f739dbee9774d645f0ac1f710eb14bf8fb932b4bc9249d1bda9f"
    )
    assert (
        digest(profile_definition("finqa_program_v2"))
        == "a5bf3804997cf0c12e648da42518f8e30151a98fbd8300a23f0536d57c502342"
    )
    assert (
        hashlib.sha256(SYSTEM_PROMPT.encode()).hexdigest()
        == "d1fb3c9b61b37b901a42fc487f7fd1999b60ca8ac16f207408b3980c03c42150"
    )
    assert (
        hashlib.sha256(SYSTEM_PROMPT_V3.encode()).hexdigest()
        == "376a55578bc84be3f17597d86274e32f367b910a70f386bdb410baced0c1fee3"
    )
    old = RunConfig(harness_id=HARNESS_ID, submission_profile="finqa_program_v2")
    assert system_message(old) == {"role": "system", "content": SYSTEM_PROMPT_V3}
    assert episode_tool_specs(old) == episode_tool_specs(config())
    previous, future = (
        profile_definition("finqa_program_v2"),
        profile_definition(STRUCTURED_PROFILE_ID),
    )
    changed = {
        key for key in previous.keys() | future.keys() if previous.get(key) != future.get(key)
    }
    assert changed == {"id", "version", "previous_profile_id", "public_assistant_output"}
    assert future["contains_task_specific_reference"] is False


@pytest.fixture(scope="module")
def tokenizer():
    assert (TOKENIZER / "tokenizer_config.json").is_file(), "NO_ADMISSION: frozen tokenizer absent"
    from transformers import AutoTokenizer

    return AutoTokenizer.from_pretrained(TOKENIZER, local_files_only=True)


@pytest.mark.parametrize("prose", ["", "I will read the table first."])
def test_actual_frozen_Qwen_template_preserves_output_contract_and_prose_counterexample(
    task, tokenizer, prose
):
    class NativeScript:
        identity = ModelIdentity(backend="scripted", model_id="structured-native-fixture")
        actual_model_calls = 0

        def __init__(self):
            self.prompts = []

        async def chat(self, messages, tools, cfg):
            validate_structured_context(messages, tools, cfg)
            rendered, _, observed = visible_envelopes(tokenizer, messages, tools)
            self.prompts.append(rendered)
            name, arguments = next_action(observed)
            raw = (
                (prose if len(self.prompts) == 1 else "")
                + "<tool_call>\n"
                + json.dumps({"name": name, "arguments": arguments})
                + "\n</tool_call>"
            )
            _, calls = parse_qwen_native_response(raw, call_prefix=f"fixture-{len(self.prompts)}")
            return ModelTurn(
                raw_text=raw,
                tool_calls=calls,
                provider_metadata={"tool_protocol": QWEN_TOOL_PROTOCOL},
            )

    provider = NativeScript()
    result = asyncio.run(run_episode(task, provider, config()))
    assert result.final_answer == "8" and result.actual_model_calls == 0
    assert canonical_assistant_message(result.turns[0])["content"] == prose
    assert system_message(config())["content"] in provider.prompts[0]
    if prose:
        assert prose in provider.prompts[1] and result.turns[0].raw_text.startswith(prose)
