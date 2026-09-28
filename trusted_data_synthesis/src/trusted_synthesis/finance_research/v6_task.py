"""V6 public program actions and lossless public evidence, not a Trace certifier.

The runtime executor receives only PublicTask. Private author references are used
exclusively by the explicitly offline native scorer below, never by a tool.
"""

from __future__ import annotations

import contextlib
import copy
import hashlib
import io
import json
from typing import Any

from .contracts import Episode, PublicTask, TaskBundle, digest
from .native_metrics import (
    _finite_execution,
    _load_finqa_scorer,
    _program_tokens,
    metric_provenance,
)
from .profiles import (
    MODEL_TERMINAL_REASONS,
    PUBLIC_REASONING_PROFILE_ID,
    PUBLIC_REASONING_V2_PROFILE_ID,
    public_run_view,
)
from .providers import canonical_assistant_message
from .settlement import episode_is_complete
from .tools import (
    TOOL_SPECS,
    VISIBLE_REFERENCE_PROTOCOL,
    PublicToolSession,
    ToolInputError,
    _fields,
)

HARNESS_ID = "bigfinance-derived-vtdo-v6"
PUBLIC_REASONING_PROFILE_BY_HARNESS = {
    HARNESS_ID: PUBLIC_REASONING_PROFILE_ID,
    "bigfinance-derived-vtdo-v7": PUBLIC_REASONING_V2_PROFILE_ID,
}


def _episode_profile(episode):
    expected = PUBLIC_REASONING_PROFILE_BY_HARNESS.get(episode.config.harness_id)
    if expected is None or episode.config.submission_profile != expected:
        raise ValueError("public-reasoning episode requires an explicit matching harness/profile")
    return expected


def public_reasoning_tool_specs() -> list[dict[str, Any]]:
    specs = copy.deepcopy(TOOL_SPECS[:2])
    for name, description in (
        (
            "run_program",
            "Execute the supplied linear FinQA program on the original public table. "
            "Returns the actual result, not correctness or an expected answer.",
        ),
        (
            "submit_program",
            "Submit the predicted program string and terminate. "
            "Records without execution; no separate answer or scale fields.",
        ),
    ):
        specs.append(
            {
                "type": "function",
                "function": {
                    "name": name,
                    "description": description
                    + " No tool handles or prev: substitution in program.",
                    "parameters": {
                        "type": "object",
                        "properties": {"program": {"type": "string"}},
                        "required": ["program"],
                        "additionalProperties": False,
                    },
                },
            }
        )
    return specs


def _public_table(task: PublicTask):
    if not isinstance(task, PublicTask):
        raise TypeError("public executor requires PublicTask, never private references")
    if task.dataset != "finqa":
        raise ToolInputError("FinQA public program executor requires a FinQA task")
    tables = [s.content for s in task.sources if s.kind == "table" and s.locator == "table"]
    if len(tables) != 1:
        raise ToolInputError("missing or ambiguous original public table")
    return tables[0]


def execute_public_program(task: PublicTask, program: str) -> dict[str, Any]:
    """Execute the original string on public evidence without reading any reference."""
    table = _public_table(task)
    if not isinstance(program, str) or not program.strip():
        raise ToolInputError("program must be a nonempty string")
    provenance = metric_provenance()
    scorer = _load_finqa_scorer()
    tokens = _program_tokens(program, scorer)
    if tokens is None:
        raise ToolInputError("invalid linear FinQA program syntax")
    invalid, result = scorer.eval_program(tokens, table)
    if invalid or not _finite_execution(result):
        raise ToolInputError("FinQA program did not execute to a finite number or yes/no")
    return {
        "program": program,
        "result": result,
        "executor_sha256": provenance["files"]["finqa_evaluate.py"]["local_sha256"],
    }


class PublicProgramSession(PublicToolSession):
    """V6 actions sharing the existing error/result-handle/identity machinery."""

    literal_argument_tools = frozenset({"run_program", "submit_program"})

    def __init__(
        self,
        task: PublicTask,
        *,
        reference_protocol=VISIBLE_REFERENCE_PROTOCOL,
        invocation_context=None,
    ):
        super().__init__(
            task, reference_protocol=reference_protocol, invocation_context=invocation_context
        )
        if reference_protocol != VISIBLE_REFERENCE_PROTOCOL:
            raise ValueError("V6 uses visible result handles")
        self.task = task

    def _validate_tool_name(self, name):
        if name not in {"list_sources", "read_source", "run_program", "submit_program"}:
            raise ToolInputError(f"unknown V6 tool: {name}")

    def _execute_extra_tool(self, name, arguments):
        _fields(arguments, {"program"})
        program = arguments["program"]
        if not isinstance(program, str) or not program.strip():
            raise ToolInputError("program must be a nonempty string")
        if name == "run_program":
            return execute_public_program(self.task, program)
        if name == "submit_program":
            return {"program": program, "submitted": True}
        raise ToolInputError(f"unknown V6 tool: {name}")


def score_public_reasoning_program(bundle: TaskBundle, episode: Episode) -> dict[str, Any]:
    """Offline pinned native metrics; never certifies public reasoning or Trace quality."""
    profile_id = _episode_profile(episode)
    if (
        episode.task_id != bundle.public.task_id
        or episode.dataset != "finqa"
        or episode.public_task_sha256 != digest(public_run_view(bundle.public, profile_id))
    ):
        raise ValueError("episode and original public source binding disagree")
    output = {
        "task_id": episode.task_id,
        "submission_profile": profile_id,
        "metric_tier": "native_program_metric_not_trace_quality",
        "native": {"execution_accuracy": None, "program_accuracy": None},
        "status": "unknown",
        "program_executable": None,
    }
    if not episode_is_complete(episode) or episode.stop_reason not in MODEL_TERMINAL_REASONS:
        return {**output, "reason": "unsettled_or_infrastructure_terminal"}
    try:
        provenance = metric_provenance()
        scorer = _load_finqa_scorer()
        table = _public_table(bundle.public)
        gold = _program_tokens(bundle.reference.program, scorer)
        if gold is None:
            return {**output, "reason": "invalid_reference_program"}
        invalid, expected = scorer.eval_program(gold, table)
        with contextlib.redirect_stdout(io.StringIO()):
            self_equal = scorer.equal_program(gold, gold)
        if (
            invalid
            or not _finite_execution(expected)
            or expected != bundle.reference.answer
            or not self_equal
        ):
            return {**output, "reason": "reference_inconsistency"}
        output["executor_sha256"] = provenance["files"]["finqa_evaluate.py"]["local_sha256"]
        program = episode.final_program
        tokens = _program_tokens(program, scorer) if isinstance(program, str) else None
        submitted = (
            episode.stop_reason == "final_answer"
            and episode.tool_events
            and episode.tool_events[-1].name == "submit_program"
            and not episode.tool_events[-1].is_error
            and episode.tool_events[-1].raw_output.get("program") == program
        )
        if not submitted or tokens is None:
            return {
                **output,
                "status": "invalid_prediction",
                "reason": "missing_or_invalid_submission",
                "program_executable": False,
                "native": {"execution_accuracy": 0.0, "program_accuracy": 0.0},
            }
        invalid, actual = scorer.eval_program(tokens, table)
        if invalid or not _finite_execution(actual):
            return {
                **output,
                "status": "invalid_prediction",
                "reason": "nonexecutable_submission",
                "program_executable": False,
                "native": {"execution_accuracy": 0.0, "program_accuracy": 0.0},
            }
        with contextlib.redirect_stdout(io.StringIO()):
            equal = scorer.equal_program(gold, tokens)
        if equal and actual != expected:
            return {**output, "reason": "reference_equivalence_execution_inconsistency"}
        return {
            **output,
            "status": "scored",
            "program_executable": True,
            "program_execution_result": actual,
            "native": {
                "execution_accuracy": float(actual == expected),
                "program_accuracy": float(equal),
            },
        }
    except Exception as error:
        # Dependency/source/scorer exceptions are not ordinary wrong model programs.
        return {**output, "reason": f"native_scoring_unavailable:{type(error).__name__}"}


def public_trajectory_view(episode: Episode, *, slot_id: str | None = None) -> dict[str, Any]:
    """Public original text with stable IDs and half-open Unicode-codepoint spans.

    No provider metadata, private reasoning, receipts, answers or references are
    projected. Native envelopes are split into their public content and original
    argument text, not duplicated as overlapping review documents. The complete
    unmodified raw response remains hash-bound in the source episode.
    """
    from .harness import episode_tool_specs, system_message

    _episode_profile(episode)
    if slot_id is not None and (not isinstance(slot_id, str) or not slot_id):
        raise ValueError("slot_id must be a nonempty string")
    if len(episode.messages) < 2 or episode.messages[0] != system_message(episode.config):
        raise ValueError("episode public system context mismatch")
    task = PublicTask.model_validate_json(episode.messages[1]["content"])
    if digest(task) != episode.public_task_sha256:
        raise ValueError("episode public source hash mismatch")
    prefix = f"{slot_id}/" if slot_id is not None else ""
    segments, sources, turns, events = [], [], [], []

    def segment(key, kind, text, **metadata):
        if not isinstance(text, str):
            raise TypeError("evidence segments must preserve original strings")
        segment_id = prefix + key
        segments.append(
            {
                "segment_id": segment_id,
                "kind": kind,
                "text": text,
                "start": 0,
                "end": len(text),
                **metadata,
            }
        )
        return segment_id

    segment("task:question", "question", task.question)
    for index, source in enumerate(task.sources):
        source_segments = []
        base = f"source:{index:04}"
        if isinstance(source.content, str):
            source_segments.append(
                segment(base + ":text", "source_text", source.content, source_id=source.source_id)
            )
        else:
            for row, cells in enumerate(source.content):
                for col, cell in enumerate(cells):
                    source_segments.append(
                        segment(
                            f"{base}:row:{row:04}:cell:{col:04}",
                            "source_table_cell",
                            cell,
                            source_id=source.source_id,
                            row=row,
                            column=col,
                        )
                    )
        sources.append(
            {
                "source_id": source.source_id,
                "kind": source.kind,
                "locator": source.locator,
                "segment_ids": source_segments,
            }
        )
    event_index = 0
    for index, turn in enumerate(episode.turns):
        base = f"turn:{index:04}"
        content = canonical_assistant_message(turn)["content"]
        content_id = segment(base + ":content", "public_content", content, turn_index=index)
        unparsed_segments = []
        api_response = turn.provider_metadata.get("api_response")
        raw_api_sha = None
        if isinstance(api_response, dict):
            raw_api = turn.provider_metadata.get("api_response_raw")
            if raw_api is not None:
                raw_api_sha = hashlib.sha256(raw_api.encode()).hexdigest()
                if (
                    raw_api_sha != turn.provider_metadata.get("raw_api_response_sha256")
                    or json.loads(raw_api) != api_response
                ):
                    raise ValueError("original API response binding changed")
            choices = api_response.get("choices", [])
            if len(choices) != 1:
                raise ValueError("public view requires one actual API response choice")
            raw_calls = choices[0].get("message", {}).get("tool_calls") or []
            if raw_calls and not turn.tool_calls:
                # This is a declared public-field projection, not invented parsed
                # action(s). It is read-only context and never a target-mask domain.
                items = raw_calls if isinstance(raw_calls, list) else [raw_calls]
                for call_index, raw_call in enumerate(items):
                    unparsed_segments.append(
                        segment(
                            f"{base}:unparsed-tool-call:{call_index:04}",
                            "unparsed_tool_call",
                            json.dumps(
                                raw_call, ensure_ascii=False, sort_keys=True, allow_nan=False
                            ),
                            turn_index=index,
                            representation="canonical_json_of_original_api_tool_call",
                            positive_target_eligible=False,
                        )
                    )
        actions = []
        for action_index, call in enumerate(turn.tool_calls):
            action_id = prefix + f"{base}:action:{action_index:04}"
            args_id = segment(
                f"{base}:action:{action_index:04}:arguments",
                "action_arguments",
                call.raw_arguments,
                turn_index=index,
                tool_name=call.name,
            )
            event_id = None
            if len(turn.tool_calls) == 1 and event_index < len(episode.tool_events):
                event = episode.tool_events[event_index]
                if (event.call_id, event.name, event.raw_arguments) != (
                    call.call_id,
                    call.name,
                    call.raw_arguments,
                ):
                    raise ValueError("event is not the actual chronological action")
                event_id = prefix + f"event:{event_index:04}"
                observation_id = segment(
                    f"event:{event_index:04}:observation",
                    "tool_observation",
                    event.visible_output,
                    event_index=event_index,
                )
                events.append(
                    {
                        "event_id": event_id,
                        "event_index": event_index,
                        "action_id": action_id,
                        "invocation_id": event.invocation_id,
                        "name": event.name,
                        "is_error": event.is_error,
                        "observation_segment_id": observation_id,
                        "result_handle": event.result_handle,
                    }
                )
                event_index += 1
            actions.append(
                {
                    "action_id": action_id,
                    "name": call.name,
                    "call_id": call.call_id,
                    "arguments_segment_id": args_id,
                    "event_id": event_id,
                }
            )
        turns.append(
            {
                "turn_id": prefix + base,
                "turn_index": index,
                "public_content_segment_id": content_id,
                "raw_response_sha256": hashlib.sha256(turn.raw_text.encode()).hexdigest(),
                "api_response_sha256": digest(api_response) if api_response is not None else None,
                "raw_api_response_sha256": raw_api_sha,
                "unparsed_tool_call_segment_ids": unparsed_segments,
                "actions": actions,
            }
        )
    if event_index != len(episode.tool_events):
        raise ValueError("unmatched actual tool events")
    body = {
        "schema": "finqa_public_trajectory.v1",
        "episode_sha256": digest(episode),
        "task_id": episode.task_id,
        "slot_id": slot_id,
        "offset_unit": "unicode_codepoint",
        "segments": segments,
        "sources": sources,
        "turns": turns,
        "events": events,
        "stop_reason": episode.stop_reason,
        "final_program": episode.final_program,
        "public_contract": {
            "system_message": system_message(episode.config),
            "tools": episode_tool_specs(episode.config),
            "submission_profile": task.answer_contract["submission_profile"],
        },
    }
    return {**body, "view_id": "public_trajectory:" + digest(body)}
