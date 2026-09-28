"""R2 through the frozen Qwen tokenizer; explicit scripts, zero model/API calls.

Tokenizer absence is a hard NO_ADMISSION failure, never a skipped positive
control. Positive-chain handles come from actual template-rendered, tokenized
and decoded tool content, not the session map. This does not test model ability.
"""

from __future__ import annotations

import asyncio
import copy
import json
import re
from pathlib import Path

import pytest

from trusted_synthesis.finance_research.contracts import (
    ModelIdentity,
    ModelTurn,
    PublicSource,
    PublicTask,
    RunConfig,
    ToolCall,
    ToolEvent,
    invocation_identity,
    invocation_scope,
)
from trusted_synthesis.finance_research.harness import HARNESS_ID, run_episode
from trusted_synthesis.finance_research.qwen_protocol import (
    QWEN_TOOL_PROTOCOL,
    parse_qwen_native_response,
)
from trusted_synthesis.finance_research.tools import VISIBLE_REFERENCE_PROTOCOL, PublicToolSession

TOKENIZER = Path(
    "/data1/zhuxinrui/models/Qwen2.5-7B-Instruct-a09a35458c702b33eeacc393d103063234e8bc28"
)


@pytest.fixture(scope="module")
def tokenizer():
    assert (TOKENIZER / "tokenizer_config.json").is_file(), "NO_ADMISSION: frozen tokenizer absent"
    from transformers import AutoTokenizer

    return AutoTokenizer.from_pretrained(TOKENIZER, local_files_only=True)


@pytest.fixture
def task():
    return PublicTask(
        dataset="finqa",
        task_id="R2_SYNTHETIC_PUBLIC_ONLY",
        version="synthetic-not-benchmark",
        question="What is current revenue minus prior revenue?",
        sources=(
            PublicSource(
                source_id="table:0",
                kind="table",
                locator="synthetic_table[0]",
                content=[["metric", "current", "prior"], ["Revenue", "120", "90"]],
            ),
        ),
    )


def call(name, args, *, technical="same.technical.content.id:0"):
    return ToolCall(name=name, arguments=args, raw_arguments=json.dumps(args), call_id=technical)


def visible_envelopes(tokenizer, messages, tools):
    rendered = tokenizer.apply_chat_template(
        messages, tools=tools, tokenize=False, add_generation_prompt=True
    )
    ids = tokenizer(rendered, add_special_tokens=False, truncation=False)["input_ids"]
    decoded = tokenizer.decode(ids, skip_special_tokens=False, clean_up_tokenization_spaces=False)
    assert decoded == rendered
    assert tokenizer(decoded, add_special_tokens=False, truncation=False)["input_ids"] == ids
    envelopes = [
        json.loads(value)
        for value in re.findall(
            r"<tool_response>\n(.*?)\n</tool_response>", decoded, flags=re.DOTALL
        )
    ]
    return decoded, ids, envelopes


class VisibleScript:
    identity = ModelIdentity(
        backend="scripted",
        model_id="R2-template-visible-fixture",
        parameter_digest="p" * 64,
        point_id="no-real-model",
    )
    actual_model_calls = 0

    def __init__(self, tokenizer, *, recovery=False):
        self.tokenizer, self.recovery = tokenizer, recovery
        self.observations, self.responses, self.rendered, self.input_ids = [], [], [], []

    async def chat(self, messages, tools, config):
        rendered, ids, seen = visible_envelopes(self.tokenizer, messages, tools)
        self.rendered.append(rendered)
        self.input_ids.append(ids)
        self.observations.append(copy.deepcopy(seen))
        assert "same.technical.content.id:0" not in rendered
        ok = [item for item in seen if item["status"] == "ok"]
        if not seen and self.recovery:
            name, arguments = "read_source", {"source_id": "nonexistent-public-source"}
        elif not ok:
            name, arguments = "read_source", {"source_id": "table:0"}
        elif "content" in ok[-1]["output"]:
            handle = ok[-1]["result_handle"]  # Actual tokenizer-decoded prompt only.
            name, arguments = (
                "calculate",
                {
                    "expression": "current-prior",
                    "variables": {
                        "current": f"prev:{handle}.output.content.1.1",
                        "prior": f"prev:{handle}.output.content.1.2",
                    },
                },
            )
        else:
            handle = ok[-1]["result_handle"]
            name, arguments = (
                "final_answer",
                {"answer": f"prev:{handle}.output.result", "program": "subtract(120, 90)"},
            )
        raw = (
            "<tool_call>\n" + json.dumps({"name": name, "arguments": arguments}) + "\n</tool_call>"
        )
        _, calls = parse_qwen_native_response(raw, call_prefix="same.technical.content.id")
        response = ModelTurn(
            raw_text=raw,
            tool_calls=calls,
            provider_metadata={
                "tool_protocol": QWEN_TOOL_PROTOCOL,
                "fixture": True,
                "original_provider_evidence": {"unchanged": True},
            },
        )
        self.responses.append(response)
        return response


@pytest.mark.parametrize("recovery", [False, True])
def test_actual_frozen_template_visible_read_calculate_final_chain(tokenizer, task, recovery):
    provider = VisibleScript(tokenizer, recovery=recovery)
    config = RunConfig(
        harness_id=HARNESS_ID,
        submission_profile="finqa_program_v2",
        role="calibration",
        max_steps=4,
        temperature=0,
    )
    context = {
        "run_id": "R2-script-positive-control",
        "episode_id": f"recovery-{recovery}",
        "attempt": 1,
    }
    journal = []
    episode = asyncio.run(
        run_episode(task, provider, config, sink=journal.append, invocation_context=context)
    )
    assert episode.final_answer == "30" and episode.stop_reason == "final_answer"
    assert episode.actual_model_calls == 0 and episode.all_provider_calls_settled
    assert episode.provider_attempts == (4 if recovery else 3)
    assert len(episode.turns) == len(episode.tool_events) == episode.provider_attempts
    assert [event.result_handle for event in episode.tool_events] == [
        f"r{index + 1}" for index in range(len(episode.tool_events))
    ]
    assert len({event.call_id for event in episode.tool_events}) == 1
    assert len({event.invocation_id for event in episode.tool_events}) == len(episode.tool_events)
    assert episode.tool_events[-2].executed_arguments["variables"] == {
        "current": "120",
        "prior": "90",
    }
    for index, (turn, event, settlement) in enumerate(
        zip(episode.turns, episode.tool_events, episode.call_settlements, strict=True)
    ):
        identity = turn.provider_metadata["harness_invocation"]
        assert (
            identity["run_id"] == context["run_id"]
            and identity["episode_id"] == context["episode_id"]
        )
        assert identity["turn_index"] == index and identity["attempt_index"] == 1
        assert identity["parameter_digest"] == provider.identity.parameter_digest
        assert turn.provider_metadata["original_provider_evidence"] == {"unchanged": True}
        assert settlement.evidence["harness_invocation"] == identity
        assert event.invocation_id != identity["invocation_id"]
        assert event.reference_protocol == VISIBLE_REFERENCE_PROTOCOL
        envelope = json.loads(event.visible_output)
        assert set(envelope) == {"result_handle", "status", "output"}
        assert envelope["output"] == event.raw_output
        if index + 1 < len(provider.observations):
            assert provider.observations[index + 1][-1] == envelope
        intent = [row for row in journal if row["kind"] == "tool_call_intent"][index]
        assert intent["payload"]["harness_invocation"]["tool_index"] == 0
        assert intent["payload"]["harness_invocation"]["invocation_id"] == event.invocation_id
    assert episode.tool_events[0].is_error is recovery
    assert '"120", "90"' in provider.rendered[0]  # Complete initial table preserved.


@pytest.mark.parametrize(
    "reference",
    [
        "prev:r1.output.content.1.1",  # Failed output.
        "prev:r999.output.result",  # Future/unknown.
        "prev:foreign-session:r2.output.result",  # No cross-session registry.
        "prev:r2.output.content.99.1",  # Missing path.
        "prev:r2.content.1.1",  # Old grammar.
        "prev:read_source.output.content.1.1",  # Tool name is not a handle.
        "prev:r2.output.content.-1.1",  # No inferred negative indexing.
    ],
)
def test_failed_unknown_future_and_bad_reference_paths_are_not_repaired(task, reference):
    session = PublicToolSession(task, reference_protocol=VISIBLE_REFERENCE_PROTOCOL)
    assert session.execute(call("read_source", {"source_id": "missing"})).is_error
    assert not session.execute(call("read_source", {"source_id": "table:0"})).is_error
    result = session.execute(call("calculate", {"expression": "x", "variables": {"x": reference}}))
    assert result.is_error and result.result_handle == "r3"
    assert result.raw_output["error"] == "ToolInputError"
    assert session.events_by_handle["r3"] == result and "r3" not in session.outputs


def test_handle_does_not_resolve_across_sessions_or_through_technical_id(task):
    first = PublicToolSession(task, reference_protocol=VISIBLE_REFERENCE_PROTOCOL)
    event = first.execute(call("read_source", {"source_id": "table:0"}))
    handle = json.loads(event.visible_output)["result_handle"]
    second = PublicToolSession(task, reference_protocol=VISIBLE_REFERENCE_PROTOCOL)
    result = second.execute(call("final_answer", {"answer": f"prev:{handle}.output.content.1.1"}))
    assert result.is_error
    assert first.execute(
        call("final_answer", {"answer": "prev:same.technical.content.id:0.output.content.1.1"})
    ).is_error
    assert not first.execute(
        call("final_answer", {"answer": f"prev:{handle}.output.content.1.1"})
    ).is_error


def test_reference_arithmetic_and_DSL_grammars_remain_distinct(task):
    session = PublicToolSession(task, reference_protocol=VISIBLE_REFERENCE_PROTOCOL)
    session.execute(call("read_source", {"source_id": "table:0"}))
    error = session.execute(call("calculate", {"expression": "prev:r1.output.content.1.1-90"}))
    assert error.is_error and "variables" in error.raw_output["message"]
    final = session.execute(
        call("final_answer", {"answer": "30", "program": "prev:r1.output.content.1.1"})
    )
    assert final.raw_output["program"] == "prev:r1.output.content.1.1"  # Literal, not repaired.
    assert not final.is_error


def test_invocation_is_coordinates_not_content_and_legacy_event_defaults_survive(task):
    one = invocation_scope({"run_id": "run", "episode_id": "episode", "attempt": 1})
    two = invocation_scope({"run_id": "run", "episode_id": "episode", "attempt": 2})
    assert (
        invocation_identity(one, turn_index=0)["invocation_id"]
        != invocation_identity(two, turn_index=0)["invocation_id"]
    )
    assert (
        invocation_identity(one, turn_index=0)["invocation_id"]
        != invocation_identity(one, turn_index=0, tool_index=0)["invocation_id"]
    )
    assert invocation_scope()["episode_id"] != invocation_scope()["episode_id"]
    old = PublicToolSession(task).execute(
        call("read_source", {"source_id": "table:0"}, technical="old_call")
    )
    raw = old.model_dump(exclude={"result_handle", "invocation_id", "reference_protocol"})
    restored = ToolEvent.model_validate(raw)
    assert restored.reference_protocol == "technical-call-id-v1"
    assert restored.result_handle is restored.invocation_id is None
    assert json.loads(restored.visible_output) == restored.raw_output
    new = PublicToolSession(task, reference_protocol=VISIBLE_REFERENCE_PROTOCOL)
    new.execute(call("read_source", {"source_id": "table:0"}), invocation_id="actual-invocation-1")
    with pytest.raises(ValueError, match="cannot execute twice"):
        new.execute(
            call("read_source", {"source_id": "table:0"}), invocation_id="actual-invocation-1"
        )


def test_h1_R_requires_explicit_new_profile_and_native_protocol(task):
    with pytest.raises(ValueError, match="requires finqa_program_v2"):
        asyncio.run(run_episode(task, VisibleScript(None), RunConfig(harness_id=HARNESS_ID)))
