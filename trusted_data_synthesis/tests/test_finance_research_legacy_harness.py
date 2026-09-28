import asyncio
import copy
import json
import threading

import pytest
from test_finance_research_datasets import finqa_record

from trusted_synthesis.finance_research.contracts import (
    ContextLimitError,
    ModelIdentity,
    ModelTurn,
    RunConfig,
)
from trusted_synthesis.finance_research.datasets import adapt_finqa
from trusted_synthesis.finance_research.legacy_harness import (
    HARNESS_ID,
    original_runtime,
    run_episode,
    runtime_binding,
)
from trusted_synthesis.finance_research.profiles import public_run_view


class Fixture:
    identity = ModelIdentity(backend="scripted", model_id="H0-CPU-fixture")
    actual_model_calls = 0

    def __init__(self, turns, *, charged_error=False):
        self.turns = iter(turns)
        self.requests, self.threads = [], []
        self.charged_error = charged_error

    async def chat(self, messages, tools, config):
        self.requests.append(copy.deepcopy(messages))
        self.threads.append(threading.get_ident())
        assert tools == []
        assert config.local_tool_protocol == "legacy-json-v1"
        value = next(self.turns)
        if isinstance(value, Exception):
            if self.charged_error:
                self.actual_model_calls += 1
            raise value
        return ModelTurn(raw_text=value)


@pytest.fixture
def task():
    return adapt_finqa([finqa_record()], split="train", revision="fixture")[0].public


def config(**kwargs):
    return RunConfig(
        harness_id=HARNESS_ID,
        local_tool_protocol="legacy-json-v1",
        submission_profile="finqa_program_v1",
        **kwargs,
    )


def test_h0_true_old_loop_clone_and_common_public_view(task):
    before_function = original_runtime._run
    before_globals = dict(original_runtime._run.__globals__)
    events = []
    provider = Fixture(
        [
            '{"tool":"read_source","arguments":{ "source_id" : "table:0" }}',
            '{"tool":"calculate","arguments":{"expression":"8-2"}}',
            '{"final":{"answer":"prev:tool:2.result","program":"subtract(8, 2)"}}',
        ]
    )
    main_thread = threading.get_ident()
    episode = asyncio.run(run_episode(task, provider, config(), sink=events.append))
    assert episode.final_answer == "6"
    assert episode.final_program == "subtract(8, 2)"
    assert episode.stop_reason == "final_answer"
    assert episode.provider_attempts == 3 and episode.actual_model_calls == 0
    assert episode.all_provider_calls_settled
    assert json.loads(provider.requests[0][1]["content"]) == public_run_view(task).model_dump(
        mode="json"
    )
    assert provider.requests[1][-1]["role"] == "user"
    assert "tool_observation" in provider.requests[1][-1]["content"]
    assert episode.tool_events[0].visible_output == provider.requests[1][-1]["content"]
    assert episode.tool_events[0].raw_arguments == '{ "source_id" : "table:0" }'
    assert all(thread == main_thread for thread in provider.threads)
    assert original_runtime._run is before_function
    assert original_runtime._run.__globals__ == before_globals
    legacy = next(event["payload"] for event in events if event["kind"] == "legacy_loop_completed")
    assert legacy["session"]["terminal"] == "first_final"
    assert legacy["runtime_binding"]["execution"].startswith("private FunctionType")
    assert legacy["inner_hardcoded_gpu_and_model_load_counters_are_not_measurements"]
    assert runtime_binding()["domain_adapter_is_new_not_old_900_task_protocol"]


def test_h0_format_and_tool_errors_remain_visible_and_old_loop_continues(task):
    provider = Fixture(
        [
            "not JSON",
            '{"tool":"calculate","arguments":{"expression":"1/0"}}',
            '{"tool":"not_registered","arguments":{}}',
            '{"final":{"answer":6,"program":"subtract(8, 2)"}}',
        ]
    )
    episode = asyncio.run(run_episode(task, provider, config()))
    assert episode.provider_attempts == 4 and episode.final_answer == 6
    assert "protocol_error" in provider.requests[1][-1]["content"]
    assert "DivisionByZero" in provider.requests[2][-1]["content"]
    assert episode.tool_events[0].visible_output == provider.requests[2][-1]["content"]
    assert "unknown_tool" in provider.requests[3][-1]["content"]
    assert [event.call_id for event in episode.tool_events] == ["tool:1", "tool:2"]
    assert all(event.is_error for event in episode.tool_events)
    assert episode.all_provider_calls_settled


@pytest.mark.parametrize("raw", ['{"final":null}', '{"final":{"answer":6}}'])
def test_h0_first_final_stops_even_malformed_or_missing_program(task, raw):
    provider = Fixture([raw, '{"final":{"answer":99}}'])
    episode = asyncio.run(run_episode(task, provider, config()))
    assert episode.stop_reason == "final_answer"
    assert episode.provider_attempts == 1
    assert episode.final_program is None
    assert episode.all_provider_calls_settled


def test_h0_response_cap_and_no_hidden_model_calls(task):
    provider = Fixture(["bad", "bad"])
    episode = asyncio.run(run_episode(task, provider, config(max_steps=2)))
    assert episode.stop_reason == "max_steps"
    assert episode.provider_attempts == 2
    assert len(episode.messages) == 6


def test_h0_post_start_timeout_is_unknown_not_complete(task):
    provider = Fixture(
        [TimeoutError("began request then disconnected"), "never called"], charged_error=True
    )
    episode = asyncio.run(run_episode(task, provider, config()))
    assert episode.actual_model_calls == 1 and episode.provider_attempts == 1
    assert episode.turns == ()
    assert episode.stop_reason == "provider_error"
    assert episode.call_settlements[0].state == "unknown"
    assert not episode.all_provider_calls_settled


def test_h0_precall_context_rejection_is_zero_charge_known_terminal(task):
    episode = asyncio.run(run_episode(task, Fixture([ContextLimitError("precall cap")]), config()))
    assert episode.stop_reason == "context_exceeded"
    assert episode.call_settlements[0].state == "pre_call_rejected"
    assert episode.all_provider_calls_settled


@pytest.mark.parametrize("failure_kind", ["model_call_intent", "tool_call_returned"])
def test_h0_durable_sink_error_propagates_without_old_loop_recovery(task, failure_kind):
    provider = Fixture(
        [
            '{"tool":"calculate","arguments":{"expression":"8-2"}}',
            '{"final":{"answer":6}}',
        ]
    )

    def sink(event):
        if event["kind"] == failure_kind:
            raise ValueError("fixture durable sink failed")

    with pytest.raises(ValueError, match="durable sink failed"):
        asyncio.run(run_episode(task, provider, config(), sink=sink))
    assert len(provider.requests) == (0 if failure_kind == "model_call_intent" else 1)


def test_h0_rejects_native_template_or_feedback_admission(task):
    with pytest.raises(ValueError, match="legacy-json"):
        asyncio.run(run_episode(task, Fixture([]), RunConfig(harness_id=HARNESS_ID)))
    with pytest.raises(ValueError, match="EVAL_NATIVE"):
        asyncio.run(run_episode(task, Fixture([]), config(tier="VTDO_FEEDBACK")))
