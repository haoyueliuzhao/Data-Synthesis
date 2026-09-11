"""Local decoder transport with unchanged public tools and first admitted Final semantics.

The local JSON transport requires Unicode scalar strings, including object keys.
Escaped lone surrogates receive interface feedback before dispatch; original output
bytes and message history stay untouched. Valid escaped surrogate pairs are accepted.
"""

from trusted_synthesis.experiments.finance_qa_vnext_thinking_comparison.online.common import (
    LIMITS,
    save,
    strict_json,
    write,
)
from trusted_synthesis.experiments.finance_qa_vnext_thinking_comparison.online.worker import (
    CalculationError,
    tool_call,
)

from .plan import SYSTEM, encode, evaluation_config, record, require, sha


def initial_messages(public):
    return [
        {"role": "system", "content": SYSTEM},
        {"role": "user", "content": encode({"task": public}).decode()},
    ]


def _require_unicode_scalars(value):
    pending = [value]
    while pending:
        current = pending.pop()
        if isinstance(current, str):
            if any(0xD800 <= ord(character) <= 0xDFFF for character in current):
                raise ValueError("response_strings_must_be_unicode_scalars")
        elif isinstance(current, dict):
            pending.extend(current)
            pending.extend(current.values())
        elif isinstance(current, list):
            pending.extend(current)


def run_session(public, directory, decoder, identity):
    config = evaluation_config()
    messages = initial_messages(public)
    calls, notebook, events, attempts = {}, {}, [], []
    terminal, final = "response_budget_exhausted", None
    for index in range(config["maximum_responses"]):
        request = {"messages": messages, "decoder_configuration_id": config["id"]}
        request_bytes = encode(request)
        if len(request_bytes) > LIMITS["request_bytes"]:
            terminal = "context_byte_limit"
            write(directory, "context_limit_request.json", request_bytes)
            break
        prefix = f"turns/{index:03d}"
        write(directory, prefix + "_request.json", request_bytes)
        outcome = decoder(messages)
        require(
            isinstance(outcome, dict) and isinstance(outcome.get("content"), str),
            "runtime.decoder_public_response",
        )
        require(type(outcome.get("generation_invoked")) is bool, "runtime.real_generation_flag")
        content = outcome["content"]
        raw = content.encode()
        if outcome["generation_invoked"]:
            write(directory, prefix + "_assistant.raw", raw)
        else:
            require(
                not raw and outcome["finish_reason"] == "context_token_limit",
                "runtime.no_fabricated_response",
            )
        outcome = record(
            "local_decoder_outcome",
            **outcome,
            response_index=index,
            request_sha256=sha(request_bytes),
            raw_response_sha256=sha(raw) if outcome["generation_invoked"] else None,
            model_identity=identity,
            origin="local_student_generation",
            is_HTTP_response=False,
        )
        save(directory, prefix + "_outcome.json", outcome)
        attempts.append(outcome)
        if outcome["finish_reason"] != "stop":
            terminal = outcome["finish_reason"]
            break
        if not content:
            terminal = "unknown_empty_public_output"
            break
        if len(raw) > LIMITS["public_content_bytes"]:
            terminal = "public_content_byte_limit"
            break
        messages.append({"role": "assistant", "content": content})
        event = {
            "response_index": index,
            "raw_sha256": sha(raw),
            "tool_call": None,
            "final": False,
            "protocol_error": None,
            "oracle_feedback": False,
        }
        try:
            choice = strict_json(content)
            _require_unicode_scalars(choice)
            if not isinstance(choice, dict):
                raise ValueError("response_must_be_json_object")
            if "final" in choice:
                event["final"] = True
                final = choice["final"]
                terminal = "model_final"
                events.append(event)
                save(directory, prefix + "_event.json", event)
                break
            if "tool" in choice:
                if len(calls) >= config["maximum_tool_calls"]:
                    terminal = "tool_budget_exhausted"
                    events.append(event)
                    save(directory, prefix + "_event.json", event)
                    break
                cid = "tool:" + str(len(calls) + 1)
                name, arguments = choice["tool"], choice.get("arguments", {})
                output = {"call_id": cid, "tool": name, "status": "ok", "result": None}
                try:
                    output["result"] = tool_call(name, arguments, public, calls, notebook)
                except (
                    CalculationError,
                    ValueError,
                    TypeError,
                    KeyError,
                    OverflowError,
                    RecursionError,
                ) as error:
                    output.update(
                        status="error",
                        error={"type": type(error).__name__, "message": str(error)[:300]},
                    )
                event["tool_call"] = {
                    "id": cid,
                    "name": name,
                    "arguments": arguments,
                    "output": output,
                }
                calls[cid] = output
                save(directory, prefix + "_tool.json", output)
                messages.append(
                    {"role": "user", "content": encode({"tool_result": output}).decode()}
                )
            else:
                messages.append(
                    {
                        "role": "user",
                        "content": encode({"receipt": "model_message_recorded"}).decode(),
                    }
                )
        except (ValueError, TypeError, KeyError, RecursionError) as error:
            event["protocol_error"] = str(error)[:300]
            messages.append(
                {
                    "role": "user",
                    "content": encode({"interface_error": event["protocol_error"]}).decode(),
                }
            )
        events.append(event)
        save(directory, prefix + "_event.json", event)
    save(directory, "messages.json", messages)
    save(directory, "notebook.json", notebook)
    result = record(
        "local_student_session",
        model_identity=identity,
        terminal=terminal,
        final=final,
        events=events,
        attempts=attempts,
        decoder_requests=len(attempts),
        model_requests=sum(item["generation_invoked"] for item in attempts),
        admitted_public_responses=len(events),
        tool_calls=len(calls),
        public_document_id=public["id"],
        public_document_sha256=sha(encode(public)),
        initial_request_messages_sha256=sha(encode(initial_messages(public))),
        no_online_answer_feedback=True,
        first_Final_stops=True,
        no_teacher_provider_calls=True,
        origin="local_student_generation",
        no_fake_HTTP_or_teacher_response_projection=True,
        original_T_and_public_tool_semantics_preserved=True,
        history_truncated=False,
    )
    save(directory, "result.json", result)
    return result
