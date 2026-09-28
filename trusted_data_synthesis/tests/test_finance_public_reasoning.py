"""V6 CPU controls: real public executor/template, mocked HTTP, no model/GPU/API."""

import asyncio
import copy
import hashlib
import json
from types import SimpleNamespace

import pytest
from test_finance_research_datasets import finqa_record
from test_finance_research_r2 import TOKENIZER, visible_envelopes

from trusted_synthesis.finance_research.contracts import ModelTurn, RunConfig, ToolCall, digest
from trusted_synthesis.finance_research.datasets import adapt_finqa
from trusted_synthesis.finance_research.harness import (
    PUBLIC_REASONING_HARNESS_ID,
    PUBLIC_REASONING_PROFILE_ID,
    SYSTEM_PROMPT,
    SYSTEM_PROMPT_V3,
    episode_tool_specs,
    public_initial_messages,
    run_episode,
    system_message,
)
from trusted_synthesis.finance_research.native_metrics import score_native
from trusted_synthesis.finance_research.profiles import profile_definition, public_run_view
from trusted_synthesis.finance_research.providers import (
    DeepSeekFlashProvider,
    ScriptedProvider,
    validate_structured_context,
)
from trusted_synthesis.finance_research.v6_task import (
    PublicProgramSession,
    execute_public_program,
    public_trajectory_view,
    score_public_reasoning_program,
)


def config(**kwargs):
    kwargs.setdefault("role", "sft")
    return RunConfig(
        harness_id=PUBLIC_REASONING_HARNESS_ID,
        submission_profile=PUBLIC_REASONING_PROFILE_ID,
        **kwargs,
    )


@pytest.fixture
def bundle():
    return adapt_finqa([finqa_record()], split="train", revision="V6-CPU-control")[0]


def call(name, arguments, call_id="action.0"):
    return ToolCall(
        name=name, arguments=arguments, raw_arguments=json.dumps(arguments), call_id=call_id
    )


class MockClient:
    def __init__(self, responses, *, private_content=None):
        self.responses, self.requests = iter(responses), []
        self.private_content = private_content

    async def post(self, url, **kwargs):
        self.requests.append(copy.deepcopy(kwargs["json"]))
        content, calls = next(self.responses)
        response = {
            "id": f"mock-{len(self.requests)}",
            "model": "deepseek-flash",
            "choices": [
                {
                    "finish_reason": "tool_calls" if calls else "stop",
                    "message": {
                        "role": "assistant",
                        "content": content,
                        "reasoning_content": self.private_content,
                        "tool_calls": [
                            {
                                "id": item.call_id,
                                "type": "function",
                                "function": {"name": item.name, "arguments": item.raw_arguments},
                            }
                            for item in calls
                        ],
                    },
                }
            ],
            "usage": {"prompt_tokens": 10, "completion_tokens": 8, "total_tokens": 18},
        }
        return SimpleNamespace(
            status_code=200, raise_for_status=lambda: None, json=lambda: response
        )


def mocked_episode(bundle, responses, **client_options):
    client = MockClient(responses, **client_options)
    episode = asyncio.run(
        run_episode(
            bundle.public,
            DeepSeekFlashProvider(api_key="mock", client=client),
            config(),
            invocation_context={"run_id": "V6-CPU", "episode_id": "chain", "attempt": 1},
        )
    )
    return episode, client


def test_public_reasoning_actual_request_executor_and_recovery(bundle):
    original = "R: Revenue increased from 2 to 8.\nQ: Check the subtraction."
    revised = "U: The divisor was zero; that program was invalid.\nR: Use subtraction."
    final = "U: The executor returned 6.\nR: Submit the difference."
    episode, client = mocked_episode(
        bundle,
        [
            (original, [call("run_program", {"program": "divide(8, 0)"})]),
            (revised, [call("run_program", {"program": "subtract(8, 2)"})]),
            (final, [call("submit_program", {"program": "subtract(8, 2)"})]),
        ],
    )
    assert episode.final_answer is None and episode.final_scale == ""
    assert episode.final_program == "subtract(8, 2)" and episode.stop_reason == "final_answer"
    assert [event.is_error for event in episode.tool_events] == [True, False, False]
    assert episode.tool_events[1].raw_output["result"] == 6
    assert episode.tool_events[2].raw_output == {"program": "subtract(8, 2)", "submitted": True}
    assert [turn.raw_text for turn in episode.turns] == [original, revised, final]
    assert client.requests[1]["messages"][2]["content"] == original
    assert client.requests[2]["messages"][4]["content"] == revised
    assert client.requests[0]["messages"] == public_initial_messages(bundle.public, config())
    assert episode.actual_model_calls == 3 and episode.all_provider_calls_settled
    replay = PublicProgramSession(
        public_run_view(bundle.public, PUBLIC_REASONING_PROFILE_ID),
        invocation_context={"run_id": "V6-CPU", "episode_id": "chain", "attempt": 1},
    )
    for turn, event, request in zip(
        episode.turns, episode.tool_events, client.requests, strict=True
    ):
        assert replay.execute(turn.tool_calls[0], invocation_id=event.invocation_id) == event
        assert turn.provider_metadata["public_request"] == request
        assert turn.provider_metadata["request_sha256"] == digest(request)
        assert turn.receipt is None
    assert "PRIVATE GOLD ANCHOR" not in json.dumps(client.requests)
    assert "PRIVATE_UNEXPOSED" not in json.dumps(client.requests)
    score = score_public_reasoning_program(bundle, episode)
    assert score["native"] == {"execution_accuracy": 1, "program_accuracy": 1}
    assert "trace" not in score and "CompletePass" not in json.dumps(score)


@pytest.mark.parametrize("content", [None, "", "untagged useful public explanation"])
def test_no_tag_or_empty_content_is_preserved_not_a_tool_execution_gate(bundle, content):
    episode, _ = mocked_episode(
        bundle, [(content, [call("submit_program", {"program": "subtract(8, 2)"})])]
    )
    assert episode.stop_reason == "final_answer"
    assert episode.turns[0].raw_text == (content or "")


@pytest.mark.parametrize(
    "calls,stop",
    [
        ([], "no_tool_call"),
        (
            [call("list_sources", {}), call("read_source", {"source_id": "missing"}, "second")],
            "multiple_tool_calls",
        ),
    ],
)
def test_no_tool_and_multiple_tools_are_retained_normal_terminals(bundle, calls, stop):
    episode, _ = mocked_episode(bundle, [("R: actual retained text", calls)])
    assert episode.stop_reason == stop and not episode.tool_events
    assert episode.turns[0].raw_text == "R: actual retained text"
    assert score_public_reasoning_program(bundle, episode)["native"]["execution_accuracy"] == 0


@pytest.mark.parametrize(
    "program",
    [
        "```subtract(8, 2)```",
        "The answer is subtract(8, 2)",
        "prev:r1.output.program",
        "__import__('os')",
        "subtract(8,2)",
        "add(#0, 1)",
    ],
)
def test_no_program_extraction_repair_or_reference_substitution(bundle, program):
    session = PublicProgramSession(bundle.public)
    assert session.execute(call("run_program", {"program": program})).is_error
    submitted = session.execute(call("submit_program", {"program": program}))
    assert not submitted.is_error and submitted.raw_output["program"] == program
    assert submitted.executed_arguments["program"] == program


def test_executor_only_public_and_no_correctness_or_old_tools(bundle, monkeypatch):
    assert execute_public_program(bundle.public, "add(8, 2)")["result"] == 10
    assert set(execute_public_program(bundle.public, "subtract(8, 2)")) == {
        "program",
        "result",
        "executor_sha256",
    }
    with pytest.raises(TypeError):
        execute_public_program(bundle, "subtract(8, 2)")
    session = PublicProgramSession(bundle.public)
    assert session.execute(call("calculate", {"expression": "8-2"})).is_error
    assert session.execute(call("final_answer", {"answer": 6})).is_error
    monkeypatch.setattr(
        "trusted_synthesis.finance_research.v6_task.execute_public_program",
        lambda *args: pytest.fail("submit must not execute"),
    )
    assert not session.execute(call("submit_program", {"program": "not a program"})).is_error


def test_public_view_spans_are_original_and_private_metadata_never_exposed(bundle):
    prose = "R: 公开收入🧮8减2。\nU: no prior tool observation."
    episode, _ = mocked_episode(
        bundle,
        [(prose, [call("submit_program", {"program": "subtract(8, 2)"})])],
        private_content="PRIVATE_UNEXPOSED",
    )
    view = public_trajectory_view(episode, slot_id="slot-0")
    segment = next(row for row in view["segments"] if row["kind"] == "public_content")
    assert segment["text"][segment["start"] : segment["end"]] == prose
    assert all(row["segment_id"].startswith("slot-0/") for row in view["segments"])
    assert "PRIVATE_UNEXPOSED" not in json.dumps(view)
    assert "PRIVATE GOLD ANCHOR" not in json.dumps(view)
    assert view["turns"][0]["actions"][0]["event_id"] == view["events"][0]["event_id"]
    assert view["events"][0]["action_id"] == view["turns"][0]["actions"][0]["action_id"]
    assert sum(row["text"] == prose for row in view["segments"]) == 1


def test_real_frozen_qwen_template_contains_original_public_content_and_result(bundle):
    from transformers import AutoTokenizer

    assert (TOKENIZER / "tokenizer_config.json").is_file(), "NO_ADMISSION: missing frozen tokenizer"
    tokenizer = AutoTokenizer.from_pretrained(TOKENIZER, local_files_only=True)
    episode, _ = mocked_episode(
        bundle,
        [
            ("R: Use 8 minus 2.", [call("run_program", {"program": "subtract(8, 2)"})]),
            ("U: Actual result is 6.", [call("submit_program", {"program": "subtract(8, 2)"})]),
        ],
    )
    rendered, ids, visible = visible_envelopes(
        tokenizer, list(episode.messages), episode_tool_specs(config())
    )
    assert "R: Use 8 minus 2." in rendered and "U: Actual result is 6." in rendered
    assert visible[0]["output"]["result"] == 6 and visible[0]["result_handle"] == "r1"
    assert len(ids) < 24576


def test_context_pairing_and_old_profile_bytes_unchanged(bundle):
    cfg = config()
    messages = public_initial_messages(bundle.public, cfg)
    validate_structured_context(messages, episode_tool_specs(cfg), cfg)
    with pytest.raises(ValueError):
        validate_structured_context(messages, episode_tool_specs(cfg), RunConfig())
    with pytest.raises(ValueError):
        system_message(cfg.model_copy(update={"harness_id": "bigfinance-derived-vtdo-v3"}))
    assert (
        hashlib.sha256(SYSTEM_PROMPT.encode()).hexdigest()
        == "d1fb3c9b61b37b901a42fc487f7fd1999b60ca8ac16f207408b3980c03c42150"
    )
    assert (
        hashlib.sha256(SYSTEM_PROMPT_V3.encode()).hexdigest()
        == "376a55578bc84be3f17597d86274e32f367b910a70f386bdb410baced0c1fee3"
    )
    assert (
        digest(profile_definition("finqa_program_v1"))
        == "618ffb0137c6f739dbee9774d645f0ac1f710eb14bf8fb932b4bc9249d1bda9f"
    )
    assert (
        digest(profile_definition("finqa_program_v2"))
        == "a5bf3804997cf0c12e648da42518f8e30151a98fbd8300a23f0536d57c502342"
    )


def test_native_unknown_is_not_model_zero(bundle):
    episode = asyncio.run(
        run_episode(bundle.public, ScriptedProvider([ModelTurn(raw_text="none")]), config())
    )
    unknown = episode.model_copy(update={"all_provider_calls_settled": False})
    assert score_public_reasoning_program(bundle, unknown)["native"]["execution_accuracy"] is None
    broken = bundle.model_copy(
        update={"reference": bundle.reference.model_copy(update={"answer": 99})}
    )
    assert score_public_reasoning_program(broken, episode)["native"]["execution_accuracy"] is None


def test_new_profile_cannot_accidentally_use_legacy_answer_program_scorer(bundle):
    with pytest.raises(ValueError, match="profile"):
        score_native(
            bundle,
            None,
            program="subtract(8, 2)",
            submission_profile=PUBLIC_REASONING_PROFILE_ID,
            stop_reason="final_answer",
            all_provider_calls_settled=True,
        )


def test_malformed_native_call_is_readonly_original_public_projection_not_action(bundle):
    malformed = ToolCall(
        call_id="broken", name="submit_program", raw_arguments="{broken", arguments={}
    )
    episode, _ = mocked_episode(
        bundle, [("R: unchanged content.", [malformed])], private_content="PRIVATE_UNEXPOSED"
    )
    assert episode.stop_reason == "no_tool_call" and not episode.turns[0].tool_calls
    view = public_trajectory_view(episode)
    turn = view["turns"][0]
    assert not turn["actions"] and not view["events"]
    assert turn["api_response_sha256"] == digest(episode.turns[0].provider_metadata["api_response"])
    docs = {row["segment_id"]: row for row in view["segments"]}
    unparsed = docs[turn["unparsed_tool_call_segment_ids"][0]]
    assert unparsed["kind"] == "unparsed_tool_call" and not unparsed["positive_target_eligible"]
    assert json.loads(unparsed["text"])["function"]["arguments"] == "{broken"
    assert "PRIVATE_UNEXPOSED" not in json.dumps(view)
