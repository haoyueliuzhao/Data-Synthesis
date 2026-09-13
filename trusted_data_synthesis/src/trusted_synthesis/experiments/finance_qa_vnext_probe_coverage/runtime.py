"""Versioned public-only runner with explicit immutable protocol selection.

The source/tool execution and first-Final rules match the original runner. No
legacy module global is patched, so parallel profiles cannot cross-contaminate.
"""

import copy

from ..finance_qa_vnext_catalog_bridge import worker as primitive
from ..finance_qa_vnext_eval_readiness.training_runtime import global_failure
from . import protocol as p


def _run(public_messages, identity, get_response, *, registered, max_responses, max_tools):
    public = primitive.public_document(public_messages, identity)
    p.require(identity == registered["identity"], "registered_public_identity")
    profile, basis = registered["profile"], registered["basis"]
    system = p.system_prompt(profile, basis)
    p.require(p.sha(system) == registered["system_prompt_sha256"], "registered_system_prompt")
    p.require(
        type(max_responses) is int
        and 1 <= max_responses <= p.MAX_RESPONSES
        and type(max_tools) is int
        and 0 <= max_tools <= p.MAX_TOOLS,
        "fixed_runtime_limits",
    )
    initial = [{"role": "system", "content": system}, *copy.deepcopy(public_messages)]
    messages, events, turns, outputs, attempts = copy.deepcopy(initial), [], [], {}, []
    terminal, first_final, final, fatal = "response_budget_exhausted", None, None, None
    for index in range(max_responses):
        context = {
            "session_id": registered["session_id"],
            "response_index": index,
            "identity": copy.deepcopy(identity),
            "requested_basis": basis,
            "protocol": p.PROTOCOL,
            "protocol_profile": profile,
            "system_prompt_sha256": registered["system_prompt_sha256"],
            "max_responses": max_responses,
            "max_tools": max_tools,
        }
        attempt = {
            "response_index": index,
            "input_messages_sha256": p.sha(p.encode(messages)),
            "context": context,
        }
        try:
            response = get_response(copy.deepcopy(messages), context)
            if isinstance(response, str):
                raw, evidence, metadata = response, None, {}
            else:
                p.require(
                    isinstance(response, dict) and isinstance(response.get("raw_response"), str),
                    "provider_public_response_contract",
                )
                raw, evidence = response["raw_response"], copy.deepcopy(response.get("evidence"))
                metadata = {
                    key: copy.deepcopy(value)
                    for key, value in response.items()
                    if key != "raw_response"
                }
            p.require(len(raw.encode()) <= p.PUBLIC_RESPONSE_BYTES, "public_response_byte_limit")
        except Exception as error:
            fatal = {
                "type": type(error).__name__,
                "message": str(error),
                "response_index": index,
                "global_fatal": global_failure(error),
            }
            attempts.append({**attempt, "status": "fatal", "error": fatal})
            terminal = (
                "fatal_provider_or_budget_stop"
                if fatal["global_fatal"]
                else "transport_session_terminal"
            )
            break
        attempts.append(
            {
                **attempt,
                "status": "public_response_received",
                "evidence": evidence,
                "raw_response_sha256": p.sha(raw),
            }
        )
        turns.append(
            {
                "response_index": index,
                "input_messages": copy.deepcopy(messages),
                "raw_response": raw,
                "raw_response_sha256": p.sha(raw),
                "transport_evidence": evidence,
                "transport_response_metadata": metadata,
                "origin": "live_teacher_callback",
            }
        )
        messages.append({"role": "assistant", "content": raw})
        event = {
            "response_index": index,
            "tool_call": None,
            "final": False,
            "protocol_error": None,
            "oracle_feedback": False,
        }
        feedback = None
        try:
            choice = primitive.strict_json(raw)
            primitive.require(isinstance(choice, dict), "response_must_be_object")
            if "final" in choice:
                terminal, first_final, final = "first_final", index, choice["final"]
                event["final"] = True
                events.append(event)
                break
            primitive.require(set(choice) == {"tool", "arguments"}, "expected_tool_or_final")
            if len(outputs) >= max_tools:
                terminal = "tool_budget_exhausted"
                events.append(event)
                break
            call_id = "tool:" + str(len(outputs) + 1)
            tool = {
                "call_id": call_id,
                "tool": choice["tool"],
                "arguments": choice["arguments"],
                "status": "ok",
                "result": None,
            }
            try:
                if tool["tool"] == "read_source":
                    tool["result"] = primitive.read_source(tool["arguments"], public)
                elif tool["tool"] == "calculate":
                    tool["result"] = primitive.calculate_with_units(tool["arguments"], outputs)
                else:
                    raise ValueError("tool.unknown_tool")
            except (
                ValueError,
                TypeError,
                KeyError,
                ZeroDivisionError,
                SyntaxError,
                RecursionError,
            ) as error:
                tool.update(status="error", error=str(error))
            outputs[call_id], event["tool_call"] = tool, copy.deepcopy(tool)
            feedback = {"tool_observation": tool}
        except (ValueError, TypeError, KeyError, RecursionError) as error:
            event["protocol_error"] = str(error)
            feedback = {
                "protocol_error": (
                    "Return one JSON tool or final object. No financial assessment was performed."
                )
            }
        events.append(event)
        messages.append({"role": "user", "content": primitive.encode(feedback).decode()})
    return p.record(
        "probe_session",
        protocol=p.PROTOCOL,
        registered_session=copy.deepcopy(registered),
        registered_session_id=registered["session_id"],
        identity=copy.deepcopy(identity),
        initial_messages=initial,
        public_messages=copy.deepcopy(public_messages),
        requested_basis=basis,
        protocol_profile=profile,
        turns=turns,
        events=events,
        terminal=terminal,
        first_final_index=first_final,
        raw_final=final,
        max_responses=max_responses,
        max_tools=max_tools,
        provider_attempts=attempts,
        provider_calls=len(attempts),
        fatal_error=fatal,
        global_fatal=bool(fatal and fatal["global_fatal"]),
        origin="live_teacher_callback",
        callback_origin_is_not_authentication=True,
        authentic_Probe_origin_verified=False,
        training_eligible=False,
        training_samples=0,
        model_weight_loads=0,
        gpu_calls=0,
        private_oracle_access=False,
    )


def generate(
    public_messages,
    identity,
    *,
    provider,
    registered,
    max_responses=p.MAX_RESPONSES,
    max_tools=p.MAX_TOOLS,
):
    p.require(callable(provider), "explicit_provider")
    return _run(
        public_messages,
        identity,
        provider,
        registered=registered,
        max_responses=max_responses,
        max_tools=max_tools,
    )


def replay(session):
    p.checked(session, "probe_session")
    p.require(session["protocol"] == p.PROTOCOL, "replay_protocol")
    turns = iter(session["turns"])

    def supplied(messages, context):
        try:
            turn = next(turns)
        except StopIteration:
            error = session.get("fatal_error")
            if error is None:
                raise ValueError("probe01.replay_missing_response") from None
            replay_error = RuntimeError(error["message"])
            replay_error.global_fatal = error["global_fatal"]
            raise replay_error from None
        p.require(messages == turn["input_messages"], "replay_exact_request_history")
        p.require(context["response_index"] == turn["response_index"], "replay_response_order")
        metadata = turn["transport_response_metadata"]
        return (
            {"raw_response": turn["raw_response"], **metadata} if metadata else turn["raw_response"]
        )

    rebuilt = _run(
        session["public_messages"],
        session["identity"],
        supplied,
        registered=session["registered_session"],
        max_responses=session["max_responses"],
        max_tools=session["max_tools"],
    )
    if session["fatal_error"]:
        rebuilt["fatal_error"] = copy.deepcopy(session["fatal_error"])
        rebuilt["provider_attempts"][-1]["error"] = copy.deepcopy(session["fatal_error"])
        rebuilt = p.record(
            "probe_session",
            **{k: v for k, v in rebuilt.items() if k not in {"id", "schema_version"}},
        )
    p.require(rebuilt == session, "complete_raw_public_history_and_tool_replay")
    return rebuilt
