"""Native protocol controls, including the installed real tokenizer (no model)."""

import json
import os
from pathlib import Path

import pytest

from trusted_synthesis.finance_research.contracts import ModelTurn
from trusted_synthesis.finance_research.providers import canonical_assistant_message
from trusted_synthesis.finance_research.qwen_protocol import (
    QWEN_TOOL_PROTOCOL,
    parse_qwen_native_response,
)


def envelope(body):
    return "<tool_call>\n" + body + "\n</tool_call>"


def turn(raw):
    _, calls = parse_qwen_native_response(raw, call_prefix="test")
    return ModelTurn(
        raw_text=raw, tool_calls=calls, provider_metadata={"tool_protocol": QWEN_TOOL_PROTOCOL}
    )


def test_exact_arguments_and_prefix_survive_without_duplicate_envelope():
    arguments = '{ "source_id" : "table-1", "nested": {"note": "literal </tool_call>"} }'
    prefix = "I will read this source.\n"
    raw = prefix + envelope('{"name": "read_source", "arguments": ' + arguments + "}")
    response = turn(raw)
    assert response.tool_calls[0].raw_arguments == arguments
    canonical = canonical_assistant_message(response)
    assert canonical["content"] == prefix
    assert canonical["tool_calls"][0]["function"]["arguments"] == json.loads(arguments)
    assert response.raw_text == raw


@pytest.mark.parametrize(
    "raw",
    [
        '{"name":"list_sources","arguments":{}}',
        '<tool_call>{"name":"list_sources","arguments":{}}',
        '{"name":"list_sources","arguments":{}}</tool_call>',
        envelope('{"name":"list_sources","arguments":{broken}'),
        envelope('{"name":"list_sources","arguments":{"x":1,"x":2}}'),
        envelope('{"name":"list_sources","arguments":{"x":NaN}}'),
        envelope('{"name":"list_sources","arguments":{"x":1e400}}'),
        envelope('{"name":"list_sources"}'),
        envelope('{"name":"list_sources","arguments":"{}"}'),
        envelope('{"name":"list_sources","arguments":[]}'),
        envelope('{"name":"","arguments":{}}'),
        envelope('{"name":"list_sources","arguments":{},"extra":1}'),
        envelope('{"tool_calls":[{"name":"list_sources","arguments":{}}]}'),
        envelope('{"name":"list_sources","arguments":{}}') + " trailing prose",
        "</tool_call>" + envelope('{"name":"list_sources","arguments":{}}'),
        envelope('{"name":"list_sources","arguments":{}}') + "<tool_call>{broken",
    ],
)
def test_invalid_native_output_is_not_repaired_or_partially_executed(raw):
    content, calls = parse_qwen_native_response(raw, call_prefix="bad")
    assert content == raw and not calls
    assert canonical_assistant_message(turn(raw)) == {"role": "assistant", "content": raw}


def test_multiple_complete_calls_are_exposed_for_harness_rejection():
    raw = (
        envelope('{"name":"list_sources","arguments":{}}')
        + "\n"
        + envelope('{"name":"read_source","arguments":{"source_id":"table-1"}}')
    )
    _, calls = parse_qwen_native_response(raw, call_prefix="multi")
    assert len(calls) == 2 and [c.call_id for c in calls] == ["multi:0", "multi:1"]


def test_canonical_refuses_fabricated_call_that_disagrees_with_raw():
    response = turn(envelope('{"name":"list_sources","arguments":{}}'))
    with pytest.raises(ValueError, match="disagrees"):
        canonical_assistant_message(response.model_copy(update={"tool_calls": ()}))


def test_real_qwen25_tokenizer_native_history_round_trip():
    transformers = pytest.importorskip("transformers")
    location = Path(
        os.environ.get(
            "FINANCE_QWEN_TOKENIZER",
            "/data1/zhuxinrui/models/Qwen2.5-7B-Instruct-a09a35458c702b33eeacc393d103063234e8bc28",
        )
    )
    if not location.is_dir():
        pytest.skip("real Qwen2.5 tokenizer is not locally installed")
    tokenizer = transformers.AutoTokenizer.from_pretrained(location, local_files_only=True)
    tools = [
        {
            "type": "function",
            "function": {
                "name": "read_source",
                "description": "Read an unchanged public source.",
                "parameters": {"type": "object", "properties": {"source_id": {"type": "string"}}},
            },
        }
    ]
    raw = "Read the source first." + envelope(
        '{"name":"read_source","arguments":{"source_id":"table-1"}}'
    )
    canonical = canonical_assistant_message(turn(raw))
    messages = [
        {"role": "system", "content": "Use one tool."},
        {"role": "user", "content": "Question"},
        canonical,
        {"role": "tool", "tool_call_id": "test:0", "content": '{"value": 42}'},
    ]
    rendered = tokenizer.apply_chat_template(
        messages, tools=tools, tokenize=False, add_generation_prompt=True
    )
    assert rendered.count("\n<tools>\n") == 1
    assert rendered.count("Read an unchanged public source.") == 1
    assert "Available tools (JSON schemas)" not in rendered
    assistant = rendered.split("<|im_start|>assistant\n")[1].split("<|im_end|>")[0]
    assert assistant.count("<tool_call>") == assistant.count("</tool_call>") == 1
    prefix, reparsed = parse_qwen_native_response(assistant, call_prefix="rerendered")
    assert prefix.rstrip() == "Read the source first."
    assert reparsed[0].arguments == {"source_id": "table-1"}
    assert json.loads(reparsed[0].raw_arguments) == {"source_id": "table-1"}
    assert '<tool_response>\n{"value": 42}\n</tool_response>' in rendered
    assert rendered.endswith("<|im_start|>assistant\n")
    assert tokenizer(rendered, add_special_tokens=False)["input_ids"]
    # H0 renders the identical tokenizer's plain-message branch, without tools=.
    legacy_raw = '{"tool":"read_source","arguments":{"source_id":"table-1"}}'
    legacy_messages = [
        {"role": "system", "content": "Use the registered old JSON grammar."},
        {"role": "user", "content": "Question"},
        {"role": "assistant", "content": legacy_raw},
        {"role": "user", "content": '{"observation":{"value":42}}'},
    ]
    legacy = tokenizer.apply_chat_template(
        legacy_messages, tokenize=False, add_generation_prompt=True
    )
    assert "# Tools" not in legacy and "<tool_call>" not in legacy
    assert legacy.count(legacy_raw) == 1
    assert legacy.endswith("<|im_start|>assistant\n")
