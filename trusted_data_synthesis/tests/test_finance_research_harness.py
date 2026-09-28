from __future__ import annotations

import asyncio
import copy
import json

import pytest

from trusted_synthesis.finance_research.contracts import (
    ContextLimitError,
    ModelIdentity,
    ModelTurn,
    PublicSource,
    PublicTask,
    RunConfig,
    ToolCall,
)
from trusted_synthesis.finance_research.harness import run_episode


class FixtureProvider:
    identity = ModelIdentity(backend="scripted", model_id="test-fixture-no-model")
    actual_model_calls = 0

    def __init__(self, responses):
        self.responses = iter(responses)
        self.requests = []

    async def chat(self, messages, tools, config):
        self.requests.append(copy.deepcopy(messages))
        response = next(self.responses)
        if isinstance(response, Exception):
            raise response
        return response


def turn(name, arguments, call_id="call_1"):
    return ModelTurn(
        raw_text="raw model text",
        tool_calls=(
            ToolCall(
                name=name, arguments=arguments, raw_arguments=json.dumps(arguments), call_id=call_id
            ),
        ),
    )


@pytest.fixture
def task():
    return PublicTask(
        dataset="fixture",
        task_id="one",
        version="fixture-v1",
        question="What is 120 / 2?",
        sources=(
            PublicSource(
                source_id="table", kind="table", locator="table[0]", content=[["revenue", "120"]]
            ),
            PublicSource(
                source_id="text",
                kind="text",
                locator="pre_text[0]",
                content="Raw public context. " * 100,
            ),
        ),
    )


def test_complete_public_history_strict_final_and_durable_event_order(task):
    provider = FixtureProvider(
        [
            turn("calculate", {"expression": "120 / 2"}),
            turn("final_answer", {"answer": "prev:call_1.result"}, "call_2"),
        ]
    )
    events = []
    result = asyncio.run(run_episode(task, provider, sink=events.append))
    assert result.stop_reason == "final_answer" and result.final_answer == "60"
    assert result.provider_attempts == 2 and result.actual_model_calls == 0
    assert json.loads(provider.requests[0][1]["content"]) == task.model_dump(mode="json")
    assert provider.requests[1][:2] == provider.requests[0]
    assert provider.requests[1][2]["tool_calls"][0]["function"]["arguments"] == {
        "expression": "120 / 2"
    }
    assert provider.requests[1][3]["content"] == result.tool_events[0].visible_output
    assert [event["kind"] for event in events] == [
        "episode_started",
        "model_call_intent",
        "model_call_returned",
        "tool_call_intent",
        "tool_call_returned",
        "model_call_intent",
        "model_call_returned",
        "tool_call_intent",
        "tool_call_returned",
        "episode_completed",
    ]


def test_plain_text_is_not_answer_and_no_hidden_continue(task):
    provider = FixtureProvider([ModelTurn(raw_text="60")])
    result = asyncio.run(run_episode(task, provider))
    assert result.stop_reason == "no_tool_call" and result.final_answer is None
    assert len(provider.requests) == 1 and len(result.messages) == 3


def test_multiple_tool_calls_fail_without_executing_any(task):
    response = ModelTurn(
        raw_text="",
        tool_calls=turn("final_answer", {"answer": "60"}).tool_calls
        + turn("calculate", {"expression": "1 / 0"}, "call_2").tool_calls,
    )
    result = asyncio.run(run_episode(task, FixtureProvider([response])))
    assert result.stop_reason == "multiple_tool_calls"
    assert result.final_answer is None and result.tool_events == ()


def test_error_is_visible_then_next_real_turn_can_correct(task):
    provider = FixtureProvider(
        [
            turn("calculate", {"expression": "1 / 0"}),
            turn("final_answer", {"answer": ["span one", "span two"]}, "call_2"),
        ]
    )
    result = asyncio.run(run_episode(task, provider))
    assert result.tool_events[0].is_error
    assert "DivisionByZero" in provider.requests[1][-1]["content"]
    assert result.final_answer == ["span one", "span two"]


@pytest.mark.parametrize(
    "exception, reason",
    [
        (ContextLimitError("over cap"), "context_exceeded"),
        (RuntimeError("offline fixture failure"), "provider_error"),
    ],
)
def test_provider_error_stops_without_retry_or_history_compaction(task, exception, reason):
    provider = FixtureProvider([exception])
    events = []
    result = asyncio.run(run_episode(task, provider, sink=events.append))
    assert result.stop_reason == reason and result.provider_attempts == 1
    assert len(provider.requests) == 1 and result.turns == ()
    assert events[-2]["kind"] == "model_call_failed"


def test_max_step_budget_and_no_receipt_fabrication(task):
    result = asyncio.run(
        run_episode(task, FixtureProvider([turn("list_sources", {})]), RunConfig(max_steps=1))
    )
    assert result.stop_reason == "max_steps" and result.final_answer is None
    assert result.turns[0].receipt is None


def test_feedback_cannot_use_scripted_receiptless_turn(task):
    result = asyncio.run(
        run_episode(
            task,
            FixtureProvider([turn("final_answer", {"answer": "60"})]),
            RunConfig(tier="VTDO_FEEDBACK", role="feedback"),
        )
    )
    assert result.stop_reason == "receipt_error" and result.tool_events == ()
    assert result.final_answer is None and len(result.turns) == 1


def test_sink_failure_prevents_call_and_is_not_retried(task):
    provider = FixtureProvider([turn("final_answer", {"answer": "60"})])

    def sink(event):
        if event["kind"] == "model_call_intent":
            raise OSError("durable store unavailable")

    with pytest.raises(OSError, match="durable store"):
        asyncio.run(run_episode(task, provider, sink=sink))
    assert provider.requests == []


def test_async_sink_and_optional_program(task):
    recorded = []

    async def sink(event):
        recorded.append(event)

    result = asyncio.run(
        run_episode(
            task,
            FixtureProvider(
                [turn("final_answer", {"answer": "60", "program": "divide(120, const_2)"})]
            ),
            sink=sink,
        )
    )
    assert result.final_program == "divide(120, const_2)"
    assert recorded[-1]["payload"]["final_program"] == result.final_program


def test_provider_without_actual_counter_has_unknown_actual_calls(task):
    class UnmeteredProvider:
        identity = FixtureProvider.identity

        async def chat(self, messages, tools, config):
            return turn("final_answer", {"answer": "60"})

    result = asyncio.run(run_episode(task, UnmeteredProvider()))
    assert result.actual_model_calls is None and result.provider_attempts == 1
    assert not result.all_provider_calls_settled
    assert result.call_settlements[0].actual_model_calls is None


def test_reject_private_or_bundled_inputs(task):
    with pytest.raises(TypeError):
        asyncio.run(run_episode({"public": task, "reference": "secret"}, FixtureProvider([])))
