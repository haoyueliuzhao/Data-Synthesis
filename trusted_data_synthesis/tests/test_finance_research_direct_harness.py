import asyncio
import copy
import json

import pytest
from test_finance_research_datasets import finqa_record

from trusted_synthesis.finance_research.contracts import (
    ContextLimitError,
    ModelIdentity,
    ModelTurn,
    RunConfig,
)
from trusted_synthesis.finance_research.datasets import adapt_finqa
from trusted_synthesis.finance_research.direct_harness import HARNESS_ID, run_episode
from trusted_synthesis.finance_research.native_metrics import score_native
from trusted_synthesis.finance_research.profiles import PUBLIC_PROFILE_V2, public_run_view
from trusted_synthesis.finance_research.settlement import episode_is_complete


class Fixture:
    identity = ModelIdentity(
        backend="scripted",
        model_id="direct-CPU-no-generation",
        parameter_digest="fixture-parameter",
    )
    actual_model_calls = 0

    def __init__(self, response, *, started_failure=False, metadata=None):
        self.response, self.started_failure, self.metadata = (
            response,
            started_failure,
            metadata or {},
        )
        self.requests = []

    async def chat(self, messages, tools, config):
        self.requests.append(dict(messages=copy.deepcopy(messages), tools=copy.deepcopy(tools)))
        if isinstance(self.response, Exception):
            self.actual_model_calls += int(self.started_failure)
            raise self.response
        return ModelTurn(raw_text=self.response, provider_metadata=self.metadata)


@pytest.fixture
def bundle():
    return adapt_finqa([finqa_record()], split="train", revision="fixture")[0]


def config(**kwargs):
    values = dict(
        harness_id=HARNESS_ID,
        local_tool_protocol="direct-json-v1",
        submission_profile=PUBLIC_PROFILE_V2,
        max_steps=1,
        temperature=0,
        role="calibration",
    )
    return RunConfig(**{**values, **kwargs})


def native(bundle, episode):
    return score_native(
        bundle,
        episode.final_answer,
        program=episode.final_program,
        submission_profile=PUBLIC_PROFILE_V2,
        stop_reason=episode.stop_reason,
        all_provider_calls_settled=episode.all_provider_calls_settled,
    )


def test_direct_one_shot_original_public_sources_no_tools_and_actual_event_order(bundle):
    raw = '{"answer":"6", "program":"subtract(8, 2)"}'
    provider, events = Fixture(raw, metadata={"provider_note": "retained"}), []
    result = asyncio.run(
        run_episode(
            bundle.public,
            provider,
            config(),
            sink=events.append,
            invocation_context={"run_id": "run-A", "episode_id": "episode-A", "attempt": 1},
        )
    )
    assert result.stop_reason == "final_answer"
    assert result.final_program == "subtract(8, 2)" and result.final_answer == "6"
    assert result.provider_attempts == 1 and len(provider.requests) == 1
    assert result.actual_model_calls == 0 and episode_is_complete(result)
    assert result.tool_events == () and provider.requests[0]["tools"] == []
    assert [m["role"] for m in provider.requests[0]["messages"]] == ["system", "user"]
    assert json.loads(provider.requests[0]["messages"][1]["content"]) == public_run_view(
        bundle.public, PUBLIC_PROFILE_V2
    ).model_dump(mode="json")
    assert result.turns[0].raw_text == raw and result.messages[-1]["content"] == raw
    assert result.turns[0].provider_metadata["provider_note"] == "retained"
    assert [event["kind"] for event in events] == [
        "episode_started",
        "model_call_intent",
        "model_call_returned",
        "episode_completed",
    ]
    invocation = events[1]["payload"]["harness_invocation"]
    assert invocation["run_id"] == "run-A" and invocation["episode_id"] == "episode-A"
    assert invocation["turn_index"] == 0 and invocation["attempt_index"] == 1
    assert invocation["parameter_digest"] == "fixture-parameter"
    assert result.turns[0].provider_metadata["harness_invocation"] == invocation
    assert result.call_settlements[0].evidence["harness_invocation"] == invocation
    assert native(bundle, result)["native"] == {"execution_accuracy": 1, "program_accuracy": 1}


@pytest.mark.parametrize(
    "raw",
    [
        '```json\n{"answer":6,"program":"subtract(8, 2)"}\n```',
        '{"final":{"answer":6,"program":"subtract(8, 2)"}}',
        '{"answer":6}',
        '{"program":"subtract(8, 2)"}',
        '{"answer":6,"answer":7,"program":"subtract(8, 2)"}',
        '{"answer":6,"program":"subtract(8, 2)"} trailing',
        '{"answer":1e400,"program":"subtract(8, 2)"}',
        '{"answer":6,"program":null}',
        "subtract(8, 2)",
    ],
)
def test_direct_invalid_or_missing_submission_is_settled_zero_without_repair_or_retry(bundle, raw):
    provider = Fixture(raw)
    result = asyncio.run(run_episode(bundle.public, provider, config()))
    assert result.stop_reason == "max_steps"
    assert result.error.startswith("invalid_direct_submission:")
    assert episode_is_complete(result) and result.tool_events == ()
    assert len(provider.requests) == 1 and result.turns[0].raw_text == raw
    assert native(bundle, result)["native"] == {"execution_accuracy": 0, "program_accuracy": 0}


def test_direct_valid_outer_json_does_not_repair_invalid_inner_program(bundle):
    result = asyncio.run(
        run_episode(bundle.public, Fixture('{"answer":6,"program":"subtract(8,2)"}'), config())
    )
    assert result.stop_reason == "final_answer" and result.final_program == "subtract(8,2)"
    assert native(bundle, result)["native"] == {"execution_accuracy": 0, "program_accuracy": 0}


def test_direct_unknown_started_timeout_remains_incomplete_with_invocation_evidence(bundle):
    provider = Fixture(TimeoutError("mock started then no response"), started_failure=True)
    result = asyncio.run(
        run_episode(
            bundle.public,
            provider,
            config(),
            invocation_context={"run_id": "run-B", "episode_id": "episode-B", "attempt": 1},
        )
    )
    assert result.stop_reason == "provider_error" and result.actual_model_calls == 1
    assert not episode_is_complete(result) and not result.all_provider_calls_settled
    assert result.call_settlements[0].state == "unknown"
    assert result.call_settlements[0].evidence["harness_invocation"]["run_id"] == "run-B"
    assert native(bundle, result)["status"] == "unknown"
    assert native(bundle, result)["native"]["execution_accuracy"] is None
    assert len(provider.requests) == 1


def test_direct_known_preflight_context_failure_has_zero_charge(bundle):
    result = asyncio.run(
        run_episode(bundle.public, Fixture(ContextLimitError("fixture cap")), config())
    )
    assert result.stop_reason == "context_exceeded" and result.actual_model_calls == 0
    assert result.call_settlements[0].state == "pre_call_rejected"
    assert result.all_provider_calls_settled


def test_direct_preserves_original_metadata_and_content_identity_separately(bundle):
    original = {"harness_invocation": {"original": "opaque"}, "invocation_id": "provider-original"}
    results = []
    for episode in ("one", "two"):
        results.append(
            asyncio.run(
                run_episode(
                    bundle.public,
                    Fixture('{"answer":6,"program":"subtract(8, 2)"}', metadata=original),
                    config(),
                    invocation_context={"run_id": "run-C", "episode_id": episode, "attempt": 1},
                )
            )
        )
    one, two = [row.turns[0].provider_metadata for row in results]
    assert one["provider_evidence_before_harness_invocation"] == original
    assert one["invocation_id"] == "provider-original"
    assert one["harness_invocation"]["invocation_id"] != two["harness_invocation"]["invocation_id"]
    assert results[0].turns[0].raw_text == results[1].turns[0].raw_text


@pytest.mark.parametrize(
    "change", [{"max_steps": 2}, {"temperature": 1}, {"tier": "VTDO_FEEDBACK"}]
)
def test_direct_rejects_nonregistered_generation_policy_before_call(bundle, change):
    provider = Fixture("must not be used")
    with pytest.raises(ValueError, match="one greedy"):
        asyncio.run(run_episode(bundle.public, provider, config(**change)))
    assert provider.requests == []


def test_direct_durable_intent_failure_never_calls_model(bundle):
    provider = Fixture("must not be used")

    def sink(event):
        if event["kind"] == "model_call_intent":
            raise OSError("fixture disk failure")

    with pytest.raises(OSError, match="disk failure"):
        asyncio.run(run_episode(bundle.public, provider, config(), sink=sink))
    assert provider.requests == []
