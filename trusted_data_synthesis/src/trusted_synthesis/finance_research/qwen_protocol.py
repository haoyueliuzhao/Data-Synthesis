"""Qwen2.5 native tool envelopes, without JSON repair or hidden regeneration.

The protocol permits unmodified prose before the first envelope and whitespace
between/after envelopes. Every envelope must contain exactly ``name`` and an
object-valued ``arguments``. Malformed responses remain ordinary assistant text;
none of their calls is executed. The one-call-per-turn rule belongs to the loop.
"""

from __future__ import annotations

import json
import math
import re

from .contracts import ToolCall

QWEN_TOOL_PROTOCOL = "qwen2.5-native-tool-call-v1"
_OPEN, _CLOSE = "<tool_call>", "</tool_call>"


def strict_json_decoder() -> json.JSONDecoder:
    def pairs(items):
        result = {}
        for key, item in items:
            if key in result:
                raise ValueError("duplicate JSON object key")
            result[key] = item
        return result

    def constant(value):
        raise ValueError("nonfinite JSON constant")

    def finite_float(value):
        result = float(value)
        if not math.isfinite(result):
            raise ValueError("nonfinite JSON number")
        return result

    return json.JSONDecoder(
        object_pairs_hook=pairs, parse_constant=constant, parse_float=finite_float
    )


def parse_qwen_native_response(raw: str, *, call_prefix: str) -> tuple[str, tuple[ToolCall, ...]]:
    """Return canonical prose and calls; preserve the raw response on any failure.

    Argument bytes are sliced from the original JSON. JSON string contents may
    contain literal tool-tag text; JSON boundaries, not a tag regex, delimit them.
    """
    first = raw.find(_OPEN)
    if first < 0:
        return raw, ()
    prefix = raw[:first]
    if "<tool_call" in prefix or "</tool_call" in prefix:
        return raw, ()
    decoder, calls = strict_json_decoder(), []

    def skip(index):
        while index < len(raw) and raw[index] in " \t\r\n":
            index += 1
        return index

    try:
        index = first
        while index < len(raw):
            if not raw.startswith(_OPEN, index):
                return raw, ()
            start = skip(index + len(_OPEN))
            value, end = decoder.raw_decode(raw, start)
            if (
                not isinstance(value, dict)
                or set(value) != {"name", "arguments"}
                or not isinstance(value["name"], str)
                # Qwen's native template inserts function names unescaped.
                or re.fullmatch(r"[A-Za-z_][A-Za-z0-9_-]*", value["name"]) is None
                or not isinstance(value["arguments"], dict)
            ):
                return raw, ()
            close = skip(end)
            if not raw.startswith(_CLOSE, close):
                return raw, ()
            # The full strict parse has already checked punctuation and nesting.
            member = skip(start + 1)
            argument_bytes = None
            while raw[member] != "}":
                key, key_end = decoder.raw_decode(raw, member)
                value_start = skip(skip(key_end) + 1)
                _, value_end = decoder.raw_decode(raw, value_start)
                if key == "arguments":
                    argument_bytes = raw[value_start:value_end]
                member = skip(value_end)
                if raw[member] == ",":
                    member = skip(member + 1)
            assert argument_bytes is not None
            calls.append(
                ToolCall(
                    call_id=f"{call_prefix}:{len(calls)}",
                    name=value["name"],
                    raw_arguments=argument_bytes,
                    arguments=value["arguments"],
                )
            )
            index = skip(close + len(_CLOSE))
    except (ValueError, TypeError, IndexError, RecursionError):
        return raw, ()
    return prefix, tuple(calls)
