"""Project in memory BEFORE persistence. Never save/hash private reasoning or raw HTTP bodies."""

try:
    from .common import strict_json
except ImportError:
    from common import strict_json


def project_response(raw):
    result = {
        "projection_version": "public_content_telemetry.v1",
        "is_original_http_response": False,
        "transport_body_bytes": len(raw),
        "parse_error": None,
        "id": None,
        "model": None,
        "object": None,
        "created": None,
        "system_fingerprint": None,
        "choices": [],
        "usage": None,
        "reasoning_telemetry": {
            "field_present": None,
            "is_string": None,
            "nonempty": None,
            "characters": None,
            "utf8_bytes": None,
        },
    }
    try:
        envelope = strict_json(raw)
        if not isinstance(envelope, dict):
            raise ValueError("not_object")
        for key in ("id", "model", "object", "system_fingerprint"):
            value = envelope.get(key)
            if isinstance(value, str) and len(value) <= 256:
                result[key] = value
        if type(envelope.get("created")) is int:
            result["created"] = envelope["created"]
        usage = envelope.get("usage")
        if isinstance(usage, dict):
            result["usage"] = {
                k: v
                for k, v in usage.items()
                if k
                in {
                    "prompt_tokens",
                    "completion_tokens",
                    "total_tokens",
                    "prompt_cache_hit_tokens",
                    "prompt_cache_miss_tokens",
                }
                and type(v) is int
                and v >= 0
            }
            details = usage.get("completion_tokens_details")
            if isinstance(details, dict) and type(details.get("reasoning_tokens")) is int:
                if details["reasoning_tokens"] >= 0:
                    result["usage"]["completion_tokens_details"] = {
                        "reasoning_tokens": details["reasoning_tokens"]
                    }
        choices = envelope.get("choices")
        if not isinstance(choices, list) or len(choices) != 1:
            raise ValueError("choice_count")
        choice = choices[0]
        message = choice["message"]
        reasoning = message.get("reasoning_content")
        result["reasoning_telemetry"] = {
            "field_present": "reasoning_content" in message,
            "is_string": isinstance(reasoning, str),
            "nonempty": bool(reasoning) if isinstance(reasoning, str) else None,
            "characters": len(reasoning) if isinstance(reasoning, str) else None,
            "utf8_bytes": len(reasoning.encode()) if isinstance(reasoning, str) else None,
        }
        content = message.get("content")
        result["choices"] = [
            {
                "index": choice.get("index") if type(choice.get("index")) is int else None,
                "finish_reason": choice.get("finish_reason")
                if choice.get("finish_reason")
                in {
                    "stop",
                    "length",
                    "content_filter",
                    "tool_calls",
                    "insufficient_system_resource",
                }
                else "unrecognized",
                "message": {
                    "role": "assistant" if message.get("role") == "assistant" else "invalid",
                    "content": content if isinstance(content, str) else None,
                    "native_tool_calls_present": bool(message.get("tool_calls")),
                },
            }
        ]
    except (ValueError, KeyError, TypeError, AttributeError, RecursionError, UnicodeError) as error:
        result["parse_error"] = type(error).__name__
    return result
