"""Public-only live training conversation; callback provenance is not authenticity.

This is a new 32-response / 32-tool protocol. The archived bridge's scripted
32-response / 24-tool runtime is unchanged. Replaying a transcript never sends a
request and never changes its recorded origin to a scripted-control origin.
"""

import copy
import sqlite3

from ..finance_qa_vnext_catalog_bridge import worker as primitive
from ..finance_qa_vnext_model_execution.transport import HTTPSendError
from ..finance_qa_vnext_surface_build.budget import BudgetRejected
from .transport import FatalStudyError

PROTOCOL = "fixed_AB_training_runtime.v2"
MAX_RESPONSES = 32
MAX_TOOLS = 32
SYSTEM = primitive.SYSTEM + (
    "\nProtocol fixed_AB_training_runtime.v2: at most 32 responses and 32 tools. "
    "This limit is a new live contract, not the archived 24-tool scripted contract."
)
GUIDANCE = {**primitive.GUIDANCE, "control": primitive.GUIDANCE["neutral"]}


def global_failure(error):
    return bool(
        getattr(
            error,
            "global_fatal",
            isinstance(error, (FatalStudyError, BudgetRejected, sqlite3.Error))
            or not isinstance(error, (ValueError, RuntimeError, OSError, HTTPSendError)),
        )
    )


def record(kind, **fields):
    row = {"schema_version": "eval_readiness.v2." + kind, **fields}
    return {**row, "id": kind + ":" + primitive.sha(primitive.encode(row))}


def _run(
    public_messages,
    identity,
    get_response,
    *,
    session_id,
    requested_basis,
    max_responses,
    max_tools,
):
    public = primitive.public_document(public_messages, identity)
    primitive.require(requested_basis in GUIDANCE, "training.guidance")
    primitive.require(
        isinstance(session_id, str) and bool(session_id), "training.registered_session_id"
    )
    primitive.require(
        type(max_responses) is int
        and 1 <= max_responses <= MAX_RESPONSES
        and type(max_tools) is int
        and 0 <= max_tools <= MAX_TOOLS,
        "training.new_32_response_32_tool_limits",
    )
    initial = [
        {"role": "system", "content": SYSTEM + "\n" + GUIDANCE[requested_basis]},
        *copy.deepcopy(public_messages),
    ]
    messages, events, turns, outputs, attempts = copy.deepcopy(initial), [], [], {}, []
    terminal, first_final, final = "response_budget_exhausted", None, None
    fatal = None
    for index in range(max_responses):
        context = {
            "session_id": session_id,
            "response_index": index,
            "identity": copy.deepcopy(identity),
            "requested_basis": requested_basis,
            "protocol": PROTOCOL,
            "max_responses": max_responses,
            "max_tools": max_tools,
        }
        attempt = {
            "response_index": index,
            "input_messages_sha256": primitive.sha(primitive.encode(messages)),
            "context": context,
        }
        try:
            response = get_response(copy.deepcopy(messages), context)
            if isinstance(response, str):
                raw, evidence, metadata = response, None, {}
            else:
                primitive.require(
                    isinstance(response, dict) and isinstance(response.get("raw_response"), str),
                    "training.provider_raw_response_contract",
                )
                raw, evidence = response["raw_response"], copy.deepcopy(response.get("evidence"))
                metadata = {
                    key: copy.deepcopy(value)
                    for key, value in response.items()
                    if key != "raw_response"
                }
            primitive.require(len(raw.encode()) <= 65536, "training.response_byte_limit")
        except Exception as error:
            # A fatal provider/budget/protocol boundary is an incomplete registered
            # session, not a retry opportunity or a valid zero-response sample.
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
                "raw_response_sha256": primitive.sha(raw.encode()),
            }
        )
        turns.append(
            {
                "response_index": index,
                "input_messages": copy.deepcopy(messages),
                "raw_response": raw,
                "raw_response_sha256": primitive.sha(raw.encode()),
                "transport_evidence": evidence,
                "origin": "live_teacher_callback",
            }
        )
        turns[-1]["transport_response_metadata"] = metadata
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
    return record(
        "training_session",
        protocol=PROTOCOL,
        registered_session_id=session_id,
        collection_session_id=session_id,
        identity=copy.deepcopy(identity),
        initial_messages=initial,
        public_messages=copy.deepcopy(public_messages),
        requested_basis=requested_basis,
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
        authentic_Teacher_origin_verified=False,
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
    session_id,
    requested_basis="neutral",
    max_responses=MAX_RESPONSES,
    max_tools=MAX_TOOLS,
):
    """Transport owns atomic reservations/authentication; only public messages cross."""
    primitive.require(callable(provider), "training.live_provider_required")
    return _run(
        public_messages,
        identity,
        provider,
        session_id=session_id,
        requested_basis=requested_basis,
        max_responses=max_responses,
        max_tools=max_tools,
    )


def replay(session):
    """Deterministic event/history replay of received bytes, without network/model calls."""
    primitive.require(session.get("protocol") == PROTOCOL, "training.replay_protocol")
    expected = record(
        "training_session",
        **{key: value for key, value in session.items() if key not in {"id", "schema_version"}},
    )
    primitive.require(expected == session, "training.session_content_identity")
    turns = iter(session["turns"])

    def supplied(messages, context):
        try:
            turn = next(turns)
        except StopIteration:
            error = session.get("fatal_error")
            if error is None:
                raise ValueError("training.replay_missing_original_response") from None
            # Reconstruct the fatal attempt exactly below; the event prefix still
            # receives full deterministic replay with the original boundaries.
            replay_error = RuntimeError(error["message"])
            replay_error.global_fatal = error["global_fatal"]
            raise replay_error from None
        primitive.require(
            messages == turn["input_messages"], "training.replay_original_input_history"
        )
        primitive.require(
            context["response_index"] == turn["response_index"], "training.replay_response_order"
        )
        metadata = turn["transport_response_metadata"]
        return (
            {"raw_response": turn["raw_response"], **metadata} if metadata else turn["raw_response"]
        )

    rebuilt = _run(
        session["public_messages"],
        session["identity"],
        supplied,
        session_id=session["registered_session_id"],
        requested_basis=session["requested_basis"],
        max_responses=session["max_responses"],
        max_tools=session["max_tools"],
    )
    if session.get("fatal_error"):
        rebuilt["fatal_error"] = copy.deepcopy(session["fatal_error"])
        rebuilt["provider_attempts"][-1]["error"] = copy.deepcopy(session["fatal_error"])
        rebuilt = record(
            "training_session",
            **{key: value for key, value in rebuilt.items() if key not in {"id", "schema_version"}},
        )
    primitive.require(rebuilt == session, "training.full_raw_history_and_tools_replay")
    return rebuilt
