"""V7 generic-public protocol controls. Mocked HTTP + real CPU tokenizer, no API/GPU."""

import asyncio
import hashlib
import json

import pytest
from test_finance_public_reasoning import MockClient, call
from test_finance_research_datasets import finqa_record
from test_finance_research_r2 import TOKENIZER
from test_finance_v6_encoding import mask_for

from trusted_synthesis.finance_research.contracts import RunConfig, digest
from trusted_synthesis.finance_research.datasets import adapt_finqa
from trusted_synthesis.finance_research.harness import (
    PUBLIC_REASONING_HARNESS_ID,
    PUBLIC_REASONING_PROFILE_ID,
    PUBLIC_REASONING_V7_HARNESS_ID,
    PUBLIC_REASONING_V7_PROFILE_ID,
    SYSTEM_PROMPT_V6,
    episode_tool_specs,
    public_initial_messages,
    run_episode,
    system_message,
)
from trusted_synthesis.finance_research.profiles import profile_definition, public_run_view
from trusted_synthesis.finance_research.providers import (
    DeepSeekFlashProvider,
    validate_structured_context,
)
from trusted_synthesis.finance_research.v6_encoding import encode_reviewed_probe_for_student
from trusted_synthesis.finance_research.v6_task import (
    execute_public_program,
    public_trajectory_view,
    score_public_reasoning_program,
)


@pytest.fixture
def bundle():
    return adapt_finqa([finqa_record()], split="train", revision="V7-synthetic-control")[0]


def config(**changes):
    return RunConfig(
        harness_id=PUBLIC_REASONING_V7_HARNESS_ID,
        submission_profile=PUBLIC_REASONING_V7_PROFILE_ID,
        role="sft",
        **changes,
    )


def mocked_episode(bundle, responses, **changes):
    client = MockClient(responses)
    provider = DeepSeekFlashProvider(api_key="mock-not-a-real-key", client=client)
    episode = asyncio.run(
        run_episode(
            bundle.public,
            provider,
            config(**changes),
            invocation_context={"run_id": "V7-CPU-only", "episode_id": "fixture", "attempt": 1},
        )
    )
    return episode, client


def test_v7_original_public_context_true_executor_and_submit_no_oracle(bundle):
    prose = "R: The table reports revenue 8 and 2; their difference is required."
    episode, client = mocked_episode(
        bundle,
        [
            (prose, [call("run_program", {"program": "subtract(8, 2)"})]),
            (
                "U: The actual executor returned 6.",
                [call("submit_program", {"program": "subtract(8, 2)"})],
            ),
        ],
    )
    assert episode.stop_reason == "final_answer" and episode.final_program == "subtract(8, 2)"
    assert episode.final_answer is None and episode.final_scale == ""
    assert episode.tool_events[0].raw_output["result"] == 6
    assert episode.tool_events[-1].raw_output == {"program": "subtract(8, 2)", "submitted": True}
    assert client.requests[1]["messages"][2]["content"] == prose
    assert client.requests[0]["messages"] == public_initial_messages(bundle.public, config())
    view = public_run_view(bundle.public, PUBLIC_REASONING_V7_PROFILE_ID)
    assert view.sources == bundle.public.sources and view.question == bundle.public.question
    assert "PRIVATE GOLD ANCHOR" not in json.dumps(client.requests)
    assert "PRIVATE SELECTED CONTEXT" not in json.dumps(client.requests)
    assert all(
        request["model"] == "deepseek-flash"
        and request["thinking"] == {"type": "disabled"}
        and "parallel_tool_calls" not in request
        for request in client.requests
    )
    assert [tool["function"]["name"] for tool in episode_tool_specs(config())] == [
        "list_sources",
        "read_source",
        "run_program",
        "submit_program",
    ]
    result = score_public_reasoning_program(bundle, episode)
    assert result["submission_profile"] == PUBLIC_REASONING_V7_PROFILE_ID
    assert result["native"] == {"execution_accuracy": 1, "program_accuracy": 1}
    public = public_trajectory_view(episode)
    assert public["public_contract"]["system_message"] == system_message(config())
    assert public["public_contract"]["submission_profile"]["id"] == PUBLIC_REASONING_V7_PROFILE_ID


def test_synthetic_linear_and_constant_examples_are_executed_not_assumed(bundle):
    profile = profile_definition(PUBLIC_REASONING_V7_PROFILE_ID)
    for example in profile["dsl"]["synthetic_examples"]:
        actual = execute_public_program(bundle.public, example["program"])
        assert actual["program"] == example["program"] and actual["result"] == example["result"]
    assert execute_public_program(bundle.public, "divide(1, 20)")["result"] == 0.05
    for malformed in ("1", "const_1", "add(const_1,const_0)", "divide(subtract(9, 4), const_10)"):
        with pytest.raises(ValueError):
            execute_public_program(bundle.public, malformed)
    assert "Reference scales are not uniform" in profile["dsl"]["numeric_representation"]
    assert "no universal rule" in profile["dsl"]["numeric_representation"]
    assert "no formal rereading is required" in profile["source_access"]


def test_percentage_display_does_not_trigger_host_program_or_scale_repair(bundle):
    submitted = "divide(1, 20), multiply(#0, const_100)"
    episode, _ = mocked_episode(
        bundle,
        [
            (
                "R: Model supplied percentage display.",
                [call("submit_program", {"program": submitted})],
            )
        ],
    )
    assert episode.final_program == submitted and episode.final_scale == ""
    assert episode.tool_events[0].executed_arguments["program"] == submitted
    assert score_public_reasoning_program(bundle, episode)["native"]["execution_accuracy"] == 0


def test_two_sources_require_two_actual_model_turns_no_compulsory_read(bundle):
    ids = [source.source_id for source in bundle.public.sources[:2]]
    episode, client = mocked_episode(
        bundle,
        [
            ("R: Inspect the first source.", [call("read_source", {"source_id": ids[0]})]),
            ("U: Read another source if useful.", [call("read_source", {"source_id": ids[1]})]),
            (
                "R: Submit the public difference.",
                [call("submit_program", {"program": "subtract(8, 2)"})],
            ),
        ],
    )
    assert len(client.requests) == 3 and [event.name for event in episode.tool_events] == [
        "read_source",
        "read_source",
        "submit_program",
    ]
    direct, direct_client = mocked_episode(
        bundle,
        [
            (
                "R: The original table suffices.",
                [call("submit_program", {"program": "subtract(8, 2)"})],
            )
        ],
    )
    assert direct.stop_reason == "final_answer" and len(direct_client.requests) == 1


def test_actual_parallel_calls_remain_failed_original_response_not_split_or_retried(bundle):
    ids = [source.source_id for source in bundle.public.sources[:2]]
    calls = [
        call("read_source", {"source_id": source}, call_id=f"parallel-{i}")
        for i, source in enumerate(ids)
    ]
    episode, client = mocked_episode(bundle, [("R: Actual invalid simultaneous response.", calls)])
    assert episode.stop_reason == "multiple_tool_calls" and len(client.requests) == 1
    assert not episode.tool_events and len(episode.turns[0].tool_calls) == 2
    assert episode.turns[0].raw_text == "R: Actual invalid simultaneous response."
    assert score_public_reasoning_program(bundle, episode)["native"]["execution_accuracy"] == 0


def test_v6_bytes_unchanged_and_cross_identity_new_context_rejected(bundle):
    assert (
        hashlib.sha256(SYSTEM_PROMPT_V6.encode()).hexdigest()
        == "b9c89be054feadadb6d6fc340f953cf6793c16f6fc74038c9c3bc672809a71fb"
    )
    assert (
        digest(profile_definition(PUBLIC_REASONING_PROFILE_ID))
        == "83683cb97f08a4cf47cf4fdcc96355f2c27f8f753782c26ad28852c8bec5fdab"
    )
    old = RunConfig(
        harness_id=PUBLIC_REASONING_HARNESS_ID, submission_profile=PUBLIC_REASONING_PROFILE_ID
    )
    assert system_message(old)["content"] == SYSTEM_PROMPT_V6
    new_messages = public_initial_messages(bundle.public, config())
    validate_structured_context(new_messages, episode_tool_specs(config()), config())
    with pytest.raises(ValueError):
        validate_structured_context(new_messages, episode_tool_specs(config()), old)
    with pytest.raises(ValueError):
        system_message(
            config().model_copy(update={"submission_profile": PUBLIC_REASONING_PROFILE_ID})
        )


def test_v7_actual_student_encoding_keeps_public_raw_history_and_masks(bundle):
    from transformers import AutoTokenizer

    assert (TOKENIZER / "tokenizer_config.json").is_file(), "NO_ADMISSION: missing frozen tokenizer"
    tokenizer = AutoTokenizer.from_pretrained(TOKENIZER, local_files_only=True)
    episode, _ = mocked_episode(
        bundle,
        [
            (
                "R: Use the public subtraction.",
                [call("run_program", {"program": "subtract(8, 2)"})],
            ),
            (
                "U: The actual result supports this submission.",
                [call("submit_program", {"program": "subtract(8, 2)"})],
            ),
        ],
        context_limit=1048576,
        max_new_tokens=16384,
    )
    encoded = encode_reviewed_probe_for_student(episode, mask_for(episode), tokenizer)
    assert encoded["encoding_admitted"] and encoded["context_limit"] == 24576
    assert not encoded["api_original_sampling_tokens_claimed"] and not encoded["context_truncated"]
    assert encoded["L_P"] == sum(len(row["target_ids"]) for row in encoded["rows"])
    assert "R: Use the public subtraction." in encoded["rows"][1]["rendered_prompt"]
    assert encoded["rows"][0]["layer_target_counts"]["tool"] > 0
    assert encoded["rows"][1]["layer_target_counts"]["final"] > 0
