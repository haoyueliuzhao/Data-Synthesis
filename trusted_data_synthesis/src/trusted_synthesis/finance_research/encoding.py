"""API Probe evidence and offline Student encoding are not sampling receipts.

No function here samples a model or computes feedback probabilities. API tool
arguments are carried verbatim into a registered Qwen-native envelope; this is
an explicit Student representation, never the API model's original tokenization.
"""

from __future__ import annotations

import copy
import json

from pydantic import model_validator

from .contracts import Episode, Record, TokenReceipt, digest
from .providers import _api_messages, _sha, canonical_assistant_message, tokenizer_binding
from .qwen_protocol import strict_json_decoder
from .settlement import episode_is_complete

# The feedback API continues to require the actual local sampling TokenReceipt.
# This alias documents its role; StudentEncodingRecord is deliberately unrelated.
FeedbackTokenReceipt = TokenReceipt
SUPERVISION_POLICY = "successful_public_responses_and_first_final_v1"
EOS_POLICY = "successful_response_student_eos_included_failure_eos_masked_v1"


def supervised_turns(episode: Episode) -> tuple[bool, ...]:
    """Tool success selects positive response targets, not semantic qualification."""
    events = {event.call_id: event for event in episode.tool_events}
    if len(events) != len(episode.tool_events):
        raise ValueError("duplicate tool execution identity")
    selected, final_seen = [], False
    for turn in episode.turns:
        valid = False
        if not final_seen and len(turn.tool_calls) == 1:
            call = turn.tool_calls[0]
            event = events.get(call.call_id)
            if event and (event.name != call.name or event.raw_arguments != call.raw_arguments):
                raise ValueError("executed tool event disagrees with the raw response")
            valid = bool(event and not event.is_error)
            if valid and call.name == "final_answer":
                final_seen = True
        selected.append(valid)
    if not final_seen:
        raise ValueError("positive material requires its actual first successful Final event")
    return tuple(selected)


class ProbeGenerationRecord(Record):
    """Frozen actual public requests, raw responses and executions, no invented IDs."""

    episode_sha256: str
    episode: Episode
    public_requests: tuple[dict, ...]
    generation_record_id: str
    api_sampling_token_ids_available: bool = False

    @model_validator(mode="after")
    def validate_evidence(self):
        episode = self.episode
        if self.episode_sha256 != digest(episode):
            raise ValueError("Probe episode binding mismatch")
        if episode.config.role != "sft" or episode.provider.backend != "deepseek_api":
            raise ValueError("API Probe requires an actual SFT-role API episode")
        if episode.provider.model_id != "deepseek-flash":
            raise ValueError("API Probe model must be deepseek-flash")
        if (
            not episode.turns
            or episode.actual_model_calls != len(episode.turns)
            or episode.provider_attempts != len(episode.turns)
            or episode.stop_reason != "final_answer"
            or episode.error is not None
            or episode.final_answer is None
            or not episode_is_complete(episode)
            or len(self.public_requests) != len(episode.turns)
            or self.api_sampling_token_ids_available
        ):
            raise ValueError("Probe requires settled complete real generation, not token claims")
        events = {event.call_id: event for event in episode.tool_events}
        response_ids = set()
        for index, (turn, request) in enumerate(
            zip(episode.turns, self.public_requests, strict=True)
        ):
            metadata = turn.provider_metadata
            response = metadata.get("api_response")
            if (
                turn.receipt is not None
                or request != metadata.get("public_request")
                or digest(request) != metadata.get("request_sha256")
                or request.get("model") != "deepseek-flash"
                or set(request)
                - {"model", "messages", "tools", "temperature", "top_p", "max_tokens", "stream"}
                or request.get("temperature") != episode.config.temperature
                or request.get("top_p") != episode.config.top_p
                or request.get("max_tokens") != episode.config.max_new_tokens
                or request.get("stream") is not False
                or "messages" not in request
                or not isinstance(response, dict)
                or response.get("model") not in (None, "deepseek-flash")
                or not isinstance(response.get("id"), str)
                or not response["id"]
            ):
                raise ValueError("Probe lacks original public API request/response binding")
            if response["id"] in response_ids:
                raise ValueError("one actual API response cannot fill multiple Probe turns")
            response_ids.add(response["id"])
            choices = response.get("choices", [])
            if (
                len(choices) != 1
                or (choices[0].get("message", {}).get("content") or "") != turn.raw_text
            ):
                raise ValueError("Probe raw response content mismatch")
            raw_calls = choices[0].get("message", {}).get("tool_calls", [])
            if len(raw_calls) != len(turn.tool_calls) or any(
                raw.get("function", {}).get("name") != call.name
                or raw.get("function", {}).get("arguments") != call.raw_arguments
                for raw, call in zip(raw_calls, turn.tool_calls, strict=True)
            ):
                raise ValueError("Probe raw tool arguments mismatch")
            if index + 1 < len(self.public_requests):
                if len(turn.tool_calls) != 1 or turn.tool_calls[0].call_id not in events:
                    raise ValueError("continued Probe lacks its actual tool execution")
                call = turn.tool_calls[0]
                expected = (
                    request["messages"]
                    + _api_messages([canonical_assistant_message(turn)])
                    + [
                        {
                            "role": "tool",
                            "tool_call_id": call.call_id,
                            "content": events[call.call_id].visible_output,
                        }
                    ]
                )
                if self.public_requests[index + 1]["messages"] != expected:
                    raise ValueError("Probe public history was dropped, altered or compacted")
                if self.public_requests[index + 1].get("tools") != request.get("tools"):
                    raise ValueError("Probe tool schema changed during a frozen trajectory")
        body = self.model_dump(mode="json", exclude={"generation_record_id"})
        if self.generation_record_id != "probe_generation:" + digest(body):
            raise ValueError("Probe generation record content identity mismatch")
        return self


def probe_generation_record(episode: Episode) -> ProbeGenerationRecord:
    body = dict(
        episode_sha256=digest(episode),
        episode=episode.model_dump(mode="json"),
        public_requests=tuple(
            turn.provider_metadata.get("public_request", {}) for turn in episode.turns
        ),
        api_sampling_token_ids_available=False,
    )
    return ProbeGenerationRecord(generation_record_id="probe_generation:" + digest(body), **body)


class StudentEncodingRow(Record):
    call_id: str
    public_request_sha256: str
    raw_response_sha256: str
    rendered_prompt: str
    rendered_response: str
    input_ids: tuple[int, ...]
    target_positions: tuple[int, ...]
    target_ids: tuple[int, ...]
    supervised: bool
    student_eos_appended: bool


class StudentEncodingRecord(Record):
    """Offline IDs/mask; cannot be passed to local-token feedback replay."""

    encoding_id: str
    episode_sha256: str
    generation_record_id: str
    tokenizer_digest: str
    chat_template_digest: str
    context_limit: int
    rows: tuple[StudentEncodingRow, ...]
    supervision_policy: str = SUPERVISION_POLICY
    eos_policy: str = EOS_POLICY
    encoding_origin: str = "offline_student_tokenizer_not_probe_sampling"
    api_original_sampling_tokens_claimed: bool = False
    context_truncated: bool = False

    @model_validator(mode="after")
    def validate_encoding(self):
        if (
            self.supervision_policy != SUPERVISION_POLICY
            or self.eos_policy != EOS_POLICY
            or self.encoding_origin != "offline_student_tokenizer_not_probe_sampling"
            or self.api_original_sampling_tokens_claimed
            or self.context_truncated
            or not self.rows
            or not 0 < self.context_limit <= 24576
        ):
            raise ValueError("invalid registered offline Student encoding policy")
        for row in self.rows:
            if (
                not row.input_ids
                or len(row.input_ids) > self.context_limit
                or any(type(token) is not int or token < 0 for token in row.input_ids)
                or len(row.target_ids) != len(row.target_positions)
                or any(
                    position <= 0 or position >= len(row.input_ids)
                    for position in row.target_positions
                )
                or tuple(row.input_ids[position] for position in row.target_positions)
                != row.target_ids
                or tuple(sorted(set(row.target_positions))) != row.target_positions
                or bool(row.target_ids) != row.supervised
                or row.student_eos_appended != row.supervised
            ):
                raise ValueError("invalid untruncated offline IDs/target mask")
        if self.encoding_id != "student_encoding:" + digest(
            self.model_dump(mode="json", exclude={"encoding_id"})
        ):
            raise ValueError("Student encoding content identity mismatch")
        return self


def _native_response(turn) -> str:
    # No normalized arguments, tool-output substitution, repair, or private labels.
    # Structural envelope is Student-format adaptation, not original API text.
    suffixes = [
        '<tool_call>\n{"name": '
        + json.dumps(call.name, ensure_ascii=False)
        + ', "arguments": '
        + call.raw_arguments
        + "}\n</tool_call>"
        for call in turn.tool_calls
    ]
    return turn.raw_text + (
        ("\n" if turn.raw_text else "") + "\n".join(suffixes) if suffixes else ""
    )


def _student_messages(messages):
    """Qwen requires argument objects; API's exact bytes remain in Probe evidence."""
    result = copy.deepcopy(messages)
    for message in result:
        for call in message.get("tool_calls", []):
            value = call["function"]["arguments"]
            if isinstance(value, str):
                call["function"]["arguments"] = strict_json_decoder().decode(value)
    return result


def encode_probe_for_student(probe: ProbeGenerationRecord, tokenizer, *, context_limit=24576):
    """Encode frozen public history; reject overlength without truncating any prefix.

    API EOS is unavailable. Exactly one *Student* EOS is appended to successful
    targets by policy, not reported as an observed API sample. Failed responses
    have zero targets (including EOS), but persist in later actual request history.
    """
    probe = ProbeGenerationRecord.model_validate_json(probe.model_dump_json())
    token_hash, template_hash = tokenizer_binding(tokenizer)
    eos = tokenizer.eos_token_id
    if type(eos) is not int or eos < 0:
        raise ValueError("Student encoding requires one registered EOS token")
    rows = []
    for turn, request, supervise in zip(
        probe.episode.turns, probe.public_requests, supervised_turns(probe.episode), strict=True
    ):
        prompt = tokenizer.apply_chat_template(
            _student_messages(request["messages"]),
            tools=request.get("tools", []),
            tokenize=False,
            add_generation_prompt=True,
        )
        response = _native_response(turn)
        kwargs = dict(add_special_tokens=False, truncation=False, padding=False)
        prompt_ids = tuple(tokenizer(prompt, **kwargs)["input_ids"])
        joined_ids = tuple(tokenizer(prompt + response, **kwargs)["input_ids"])
        if joined_ids[: len(prompt_ids)] != prompt_ids:
            raise ValueError("Student prompt/response boundary retokenizes; no prefix repair")
        response_ids = joined_ids[len(prompt_ids) :]
        if not prompt_ids or not response_ids:
            raise ValueError("empty offline prompt/response encoding")
        suffix = response_ids + ((eos,) if supervise else ())
        if len(prompt_ids) + len(suffix) > context_limit:
            raise ValueError("Student encoding exceeds untruncated context limit")
        rows.append(
            StudentEncodingRow(
                call_id="api_response:" + turn.provider_metadata["api_response"]["id"],
                public_request_sha256=digest(request),
                raw_response_sha256=_sha(turn.raw_text),
                rendered_prompt=prompt,
                rendered_response=response,
                input_ids=prompt_ids + suffix,
                target_positions=tuple(range(len(prompt_ids), len(prompt_ids) + len(suffix)))
                if supervise
                else (),
                target_ids=suffix if supervise else (),
                supervised=supervise,
                student_eos_appended=supervise,
            )
        )
    body = dict(
        episode_sha256=probe.episode_sha256,
        generation_record_id=probe.generation_record_id,
        tokenizer_digest=token_hash,
        chat_template_digest=template_hash,
        context_limit=context_limit,
        rows=[row.model_dump(mode="json") for row in rows],
        supervision_policy=SUPERVISION_POLICY,
        eos_policy=EOS_POLICY,
        encoding_origin="offline_student_tokenizer_not_probe_sampling",
        api_original_sampling_tokens_claimed=False,
        context_truncated=False,
    )
    return StudentEncodingRecord(encoding_id="student_encoding:" + digest(body), **body)
