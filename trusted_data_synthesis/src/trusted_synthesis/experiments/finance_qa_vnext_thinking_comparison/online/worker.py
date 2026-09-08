"""Isolated public-only continuous conversation. Final ends before any evaluator exists."""

import argparse
import http.client
import json
import os
import resource
import signal
import ssl
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from calculator import CalculationError, calculate  # noqa: E402
from common import (  # noqa: E402
    LIMITS,
    SYSTEM,
    encode,
    record,
    request_body,
    save,
    sha,
    strict_json,
    write,
)
from isolate import restrict  # noqa: E402
from projection import project_response  # noqa: E402


def tool_call(name, arguments, document, previous, notebook):
    if not isinstance(arguments, dict):
        raise ValueError("tool_arguments_must_be_object")
    if name == "calculate":
        return calculate(arguments, previous)
    if name == "read_source":
        locators = arguments.get("locators")
        if not isinstance(locators, list) or not 1 <= len(locators) <= 32:
            raise ValueError("read_source_requires_1_to_32_locators")
        facts = {f["id"]: f for f in document["numeric_catalog"]}
        rows = []
        for locator in locators:
            if not isinstance(locator, str):
                raise ValueError("invalid_locator")
            if locator in facts:
                fact = facts[locator]
                rows.append(
                    {"numeric_record": fact, "segment": document["segments"][fact["segment"]]}
                )
            elif locator in document["segments"]:
                rows.append({"segment_id": locator, "segment": document["segments"][locator]})
            else:
                raise ValueError("unknown_public_locator:" + locator[:100])
        result = {"records": rows}
        if len(locators) == 1 and locators[0] in facts:
            result.update(exact_value=facts[locators[0]]["value"], numeric_source_id=locators[0])
        return result
    if name == "notebook":
        key = arguments.get("key")
        if not isinstance(key, str) or not 0 < len(key) <= 80:
            raise ValueError("invalid_note_key")
        if arguments.get("operation") == "write":
            text = arguments.get("text")
            if not isinstance(text, str) or len(text) > 8192:
                raise ValueError("note_text_limit")
            if key not in notebook and len(notebook) >= 32:
                raise ValueError("note_count_limit")
            notebook[key] = text
            return {"key": key, "text": text, "author": "model", "operation": "write"}
        if arguments.get("operation") == "read":
            if key not in notebook:
                raise ValueError("unknown_note_key")
            return {"key": key, "text": notebook[key], "author": "model", "operation": "read"}
        raise ValueError("unknown_notebook_operation")
    raise ValueError("unknown_tool:" + str(name)[:80])


def https_request(body, credential):
    def expired(signum, frame):
        raise TimeoutError("total_http_deadline")

    previous_handler = signal.signal(signal.SIGALRM, expired)
    connection = None
    response_body = bytearray()
    started = time.monotonic_ns()
    try:
        signal.setitimer(signal.ITIMER_REAL, LIMITS["total_seconds"])
        connection = http.client.HTTPSConnection(
            "api.deepseek.com",
            timeout=LIMITS["connect_seconds"],
            context=ssl.create_default_context(),
        )
        connection.request(
            "POST",
            "/chat/completions",
            body=body,
            headers={"Content-Type": "application/json", "Authorization": "Bearer " + credential},
        )
        if connection.sock:
            connection.sock.settimeout(LIMITS["total_seconds"])
        response = connection.getresponse()
        while True:
            block = response.read(min(65536, LIMITS["response_bytes"] + 1 - len(response_body)))
            if not block:
                break
            response_body.extend(block)
            if len(response_body) > LIMITS["response_bytes"]:
                raise ValueError("http_response_size_limit")
        return {
            "status": response.status,
            "body": bytes(response_body),
            "error": None,
            "elapsed_ns": time.monotonic_ns() - started,
        }
    except (OSError, ValueError, http.client.HTTPException) as error:
        return {
            "status": None,
            "body": bytes(response_body),
            "error": type(error).__name__,
            "elapsed_ns": time.monotonic_ns() - started,
        }
    finally:
        signal.setitimer(signal.ITIMER_REAL, 0)
        signal.signal(signal.SIGALRM, previous_handler)
        if connection is not None:
            connection.close()


def generate(document, output, credential=None, scripted=None, model="deepseek-v4-flash"):
    messages = [
        {"role": "system", "content": SYSTEM},
        {"role": "user", "content": encode({"task": document}).decode()},
    ]
    outputs, notebook, events, attempts = {}, {}, [], []
    terminal, final_content = "response_budget_exhausted", None
    for index in range(LIMITS["model_responses"]):
        body = encode(request_body(messages, model))
        if len(body) > LIMITS["request_bytes"]:
            terminal = "context_byte_limit"
            write(output, "context_limit_request.body", body)
            break
        prefix = f"turns/{index:03d}"
        write(output, prefix + "_http_request.body", body)
        reservation = record(
            "attempt",
            index=index,
            request_sha256=sha(body),
            request_bytes=len(body),
            provider_call=scripted is None,
            response_limit=LIMITS["output_tokens"],
            prefix_messages=len(messages),
            reserved_token_allowance=115712,
            requested_model=model,
            started_utc=datetime.now(timezone.utc).isoformat(),
        )
        save(output, prefix + "_reservation.json", reservation)
        if scripted is not None:
            if index >= len(scripted):
                raise RuntimeError("control.script_exhausted")
            content = (
                scripted[index]
                if isinstance(scripted[index], str)
                else encode(scripted[index]).decode()
            )
            reply = {
                "status": 200,
                "error": None,
                "elapsed_ns": 0,
                "body": encode(
                    {
                        "id": f"control:{index}",
                        "object": "chat.completion",
                        "model": "scripted_control",
                        "choices": [
                            {
                                "index": 0,
                                "finish_reason": "stop",
                                "message": {"role": "assistant", "content": content},
                            }
                        ],
                    }
                ),
            }
        else:
            reply = https_request(body, credential)
        if (
            scripted is not None
            and isinstance(scripted[index], dict)
            and "_control_envelope" in scripted[index]
        ):
            reply["body"] = encode(scripted[index]["_control_envelope"])
            reply["status"] = scripted[index].get("_control_status", 200)
        projected = project_response(reply["body"])
        # Raw HTTP/private reasoning exists only in memory. No raw file or digest.
        reply.pop("body")
        save(output, prefix + "_response_projection.json", projected)
        outcome = {
            "index": index,
            "reservation_id": reservation["id"],
            "request_sha256": sha(body),
            "response_projection_sha256": sha(encode(projected)),
            "response_bytes": projected["transport_body_bytes"],
            "response_is_projection": True,
            "reasoning_telemetry": projected["reasoning_telemetry"],
            "public_content_received": False,
            "http_status": reply["status"],
            "elapsed_ns": reply["elapsed_ns"],
            "error": reply["error"],
            "origin": "live_http" if scripted is None else "scripted_control",
            "usage": projected["usage"],
            "model": projected["model"],
            "finish_reason": None,
            "public_content_returned": False,
        }
        try:
            if reply["error"] or reply["status"] != 200:
                raise ValueError("http_failure")
            envelope = projected
            if projected["parse_error"]:
                raise ValueError("provider_projection_parse_failure")
            choices = envelope["choices"]
            if len(choices) != 1 or choices[0]["index"] != 0:
                raise ValueError("provider_choices")
            message = choices[0]["message"]
            content = message["content"]
            outcome.update(
                model=envelope.get("model"),
                finish_reason=choices[0].get("finish_reason"),
                usage=envelope.get("usage"),
                provider_response_id=envelope.get("id"),
            )
            if isinstance(content, str) and len(content.encode()) <= LIMITS["public_content_bytes"]:
                write(output, prefix + "_assistant.raw", content.encode())
                outcome["public_content_received"] = True
            if (
                envelope.get("object") != "chat.completion"
                or message.get("role") != "assistant"
                or message.get("native_tool_calls_present")
                or (
                    scripted is None
                    and envelope.get("model")
                    not in {model, model + ("-0731" if model.endswith("flash") else "-0813")}
                )
            ):
                raise ValueError("provider_condition_before_length_classification")
            if choices[0].get("finish_reason") == "length":
                save(output, prefix + "_outcome.json", outcome)
                attempts.append(outcome)
                terminal = "generation_truncated_length"
                break
            if (
                choices[0].get("finish_reason") != "stop"
                or not isinstance(content, str)
                or not content
                or len(content.encode()) > LIMITS["public_content_bytes"]
                or message.get("role") != "assistant"
                or message.get("native_tool_calls_present")
                or envelope.get("object") != "chat.completion"
                or (
                    scripted is None
                    and envelope.get("model")
                    not in {model, model + ("-0731" if model.endswith("flash") else "-0813")}
                )
            ):
                raise ValueError("provider_public_content_contract")
        except (ValueError, TypeError, KeyError, IndexError, RecursionError):
            outcome["error"] = outcome["error"] or "provider_envelope_or_condition_failure"
            save(output, prefix + "_outcome.json", outcome)
            attempts.append(outcome)
            terminal = "unknown_transport_or_condition"
            break
        outcome["public_content_returned"] = True
        save(output, prefix + "_outcome.json", outcome)
        attempts.append(outcome)
        messages.append({"role": "assistant", "content": content})
        event = {
            "response_index": index,
            "raw_sha256": sha(content.encode()),
            "tool_call": None,
            "final": False,
            "protocol_error": None,
            "oracle_feedback": False,
        }
        try:
            choice = strict_json(content)
            if not isinstance(choice, dict):
                raise ValueError("response_must_be_json_object")
            # Any Final is terminal. No type, numeric, evidence, formula, or unit
            # check can cause it to be returned to the model for another attempt.
            if "final" in choice:
                event["final"] = True
                final_content = choice["final"]
                terminal = "model_final"
                events.append(event)
                save(output, prefix + "_event.json", event)
                break
            if "tool" in choice:
                if len(outputs) >= LIMITS["tool_calls"]:
                    terminal = "tool_budget_exhausted"
                    events.append(event)
                    save(output, prefix + "_event.json", event)
                    break
                call_id = "tool:" + str(len(outputs) + 1)
                name, arguments = choice["tool"], choice.get("arguments", {})
                result = {"call_id": call_id, "tool": name, "status": "ok", "result": None}
                try:
                    result["result"] = tool_call(name, arguments, document, outputs, notebook)
                except (
                    CalculationError,
                    ValueError,
                    TypeError,
                    KeyError,
                    OverflowError,
                    RecursionError,
                ) as error:
                    result.update(
                        status="error",
                        error={"type": type(error).__name__, "message": str(error)[:300]},
                    )
                event["tool_call"] = {
                    "id": call_id,
                    "name": name,
                    "arguments": arguments,
                    "output": result,
                }
                outputs[call_id] = result
                save(output, prefix + "_tool.json", result)
                messages.append(
                    {"role": "user", "content": encode({"tool_result": result}).decode()}
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
        save(output, prefix + "_event.json", event)
    save(output, "messages.json", messages)
    save(output, "notebook.json", notebook)
    result = record(
        "session_result",
        terminal=terminal,
        final=final_content,
        events=events,
        attempts=attempts,
        model_responses=sum(a["public_content_received"] for a in attempts),
        admitted_public_responses=len(events),
        requested_model=model,
        response_storage="public_projection_not_original_http",
        model_requests=len(attempts),
        tool_calls=len(outputs),
        provider_attempts=len(attempts) if scripted is None else 0,
        origin="live_http" if scripted is None else "scripted_control",
        first_final_stops=True,
        hidden_evaluator_loaded=False,
        online_answer_feedback=False,
        mandatory_accept=False,
        source_document_sha256=sha(encode(document)),
        history_truncated=False,
    )
    save(output, "result.json", result)
    members = [
        {
            "path": str(p.relative_to(output)),
            "sha256": sha(p.read_bytes()),
            "bytes": p.stat().st_size,
        }
        for p in sorted(Path(output).rglob("*"))
        if p.is_file()
    ]
    save(
        output, "manifest.json", record("worker_manifest", members=members, result_id=result["id"])
    )
    return result


def main():
    resource.setrlimit(resource.RLIMIT_CORE, (0, 0))
    parser = argparse.ArgumentParser()
    parser.add_argument("--public", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--forbidden", action="append", default=[])
    parser.add_argument("--key-fd", type=int)
    parser.add_argument("--script", type=Path)
    parser.add_argument(
        "--model", choices=["deepseek-v4-flash", "deepseek-v4-pro"], default="deepseek-v4-flash"
    )
    args = parser.parse_args()
    if args.script is None and args.key_fd is None:
        raise RuntimeError("credential.missing")
    args.output.mkdir(parents=True, exist_ok=False)
    credential = None
    if args.key_fd is not None:
        credential = os.read(args.key_fd, 4096).decode().strip()
        os.close(args.key_fd)
        if not credential or any(c in credential for c in "\r\n\x00"):
            raise RuntimeError("credential.invalid")
    isolation = restrict(
        args.public,
        args.output,
        Path(__file__).resolve().parent,
        args.forbidden,
        [args.script] if args.script else [],
    )
    ssl.create_default_context()
    isolation["tls_context_created_without_network"] = True
    isolation["core_dumps_disabled"] = True
    isolation.update(
        python=sys.version,
        isolated_mode=sys.flags.isolated,
        no_site=sys.flags.no_site,
        repository_modules_loaded=[m for m in sys.modules if m.startswith("trusted_synthesis")],
    )
    save(args.output, "isolation.json", isolation)
    document = strict_json(args.public.read_bytes())
    scripted = strict_json(args.script.read_bytes()) if args.script else None
    result = generate(document, args.output, credential, scripted, args.model)
    print(
        json.dumps(
            {
                "terminal": result["terminal"],
                "model_requests": result["model_requests"],
                "tool_calls": result["tool_calls"],
            }
        ),
        flush=True,
    )


if __name__ == "__main__":
    main()
