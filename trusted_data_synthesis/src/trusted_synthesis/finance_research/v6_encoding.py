"""V6 offline Student spans: frozen API public text, never API sampling receipts.

The consensus module supplies semantic judgments. This encoder only binds their
original-character spans to the real Student tokenizer and preserves full history.
"""

from __future__ import annotations

import copy
import hashlib
import json

from .contracts import Episode, digest
from .encoding import _native_response, _student_messages
from .harness import PUBLIC_REASONING_HARNESSES, episode_tool_specs, system_message
from .providers import _api_messages, canonical_assistant_message, tokenizer_binding
from .settlement import episode_is_complete
from .v6_task import public_trajectory_view

CONTEXT_LIMIT = 24576
ENCODING_POLICY = "v6_reviewed_public_spans_and_successful_approved_actions_v1"
EOS_POLICY = "one_student_eos_per_response_supervised_iff_action_approved_v1"


def _sha(text):
    return hashlib.sha256(text.encode()).hexdigest()


def _api_requests(episode, view):
    """Bind real public API requests without accepting local or invented receipts."""
    if (
        episode.config.harness_id not in PUBLIC_REASONING_HARNESSES
        or episode.provider.backend != "deepseek_api"
        or episode.provider.model_id != "deepseek-flash"
        or episode.config.role != "sft"
        or not episode_is_complete(episode)
        or episode.actual_model_calls != len(episode.turns)
        or episode.provider_attempts != len(episode.turns)
    ):
        raise ValueError("Student API encoding requires complete settled V6 SFT API evidence")
    events = {row["event_id"]: row for row in view["events"]}
    documents = {row["segment_id"]: row for row in view["segments"]}
    requests, response_ids = [], set()

    def has_reasoning_usage(value):
        if isinstance(value, dict):
            return any(
                (key == "reasoning_tokens" and item not in (None, 0)) or has_reasoning_usage(item)
                for key, item in value.items()
            )
        if isinstance(value, list):
            return any(has_reasoning_usage(item) for item in value)
        return False

    expected = copy.deepcopy(list(episode.messages[:2]))
    if expected[0] != system_message(episode.config):
        raise ValueError("unbound V6 initial context")
    for turn, projected in zip(episode.turns, view["turns"], strict=True):
        metadata = turn.provider_metadata
        request, response = metadata.get("public_request"), metadata.get("api_response")
        if (
            turn.receipt is not None
            or not isinstance(request, dict)
            or digest(request) != metadata.get("request_sha256")
            or request.get("model") != "deepseek-flash"
            or request.get("thinking") != {"type": "disabled"}
            or request.get("messages") != _api_messages(expected)
            or request.get("tools") != episode_tool_specs(episode.config)
            or request.get("temperature") != episode.config.temperature
            or request.get("top_p") != episode.config.top_p
            or request.get("max_tokens") != episode.config.max_new_tokens
            or request.get("stream") is not False
            or set(request)
            - {
                "model",
                "messages",
                "tools",
                "temperature",
                "top_p",
                "max_tokens",
                "stream",
                "thinking",
            }
            or not isinstance(response, dict)
        ):
            raise ValueError("unbound original public API request")
        choices = response.get("choices", [])
        response_id = response.get("id")
        if len(choices) != 1 or not isinstance(response_id, str) or not response_id:
            raise ValueError("unbound actual API response")
        if response_id in response_ids:
            raise ValueError("one API response cannot fill multiple turns")
        response_ids.add(response_id)
        message = choices[0].get("message", {})
        raw_calls = message.get("tool_calls", [])
        if (
            (message.get("content") or "") != turn.raw_text
            or message.get("reasoning_content")
            or has_reasoning_usage(response.get("usage", {}))
            or len(raw_calls) != len(turn.tool_calls)
            or any(
                raw.get("function", {}).get("name") != call.name
                or raw.get("function", {}).get("arguments") != call.raw_arguments
                for raw, call in zip(raw_calls, turn.tool_calls, strict=True)
            )
        ):
            raise ValueError("API public response changed or contains private thinking")
        requests.append(request)
        expected.append(canonical_assistant_message(turn))
        for action in projected["actions"]:
            if action["event_id"] is not None:
                event = events[action["event_id"]]
                expected.append(
                    {
                        "role": "tool",
                        "tool_call_id": action["call_id"],
                        "content": documents[event["observation_segment_id"]]["text"],
                    }
                )
    if expected != list(episode.messages):
        raise ValueError("episode actual history differs from its API request chain")
    return requests


def encode_reviewed_probe_for_student(
    episode: Episode,
    resolved_mask: dict,
    tokenizer,
    *,
    context_limit=CONTEXT_LIMIT,
) -> dict:
    """Full untruncated per-response rows; every target belongs to one whole package.

    Token boundaries crossing a reviewed span are masked. Reason and update text
    share layer ``reason``; successful approved nonfinal actions use ``tool`` and
    submit_program uses ``final``. Their appended Student EOS shares that layer.
    Failure/retracted/unknown history remains in subsequent complete prompts.
    Encoding admission is not material qualification or permission to train.
    """
    if context_limit != CONTEXT_LIMIT:
        raise ValueError("V6 Student context is fixed at 24576; no truncation variant")
    view = public_trajectory_view(episode, slot_id=resolved_mask.get("slot_id"))
    if (
        resolved_mask.get("episode_sha256") != digest(episode)
        or resolved_mask.get("view_id") != view["view_id"]
        or resolved_mask.get("not_a_TokenReceipt") is not True
        or resolved_mask.get("mask_agreement") is not True
    ):
        raise ValueError("resolved mask is not bound to this public episode and double review")
    requests = _api_requests(episode, view)
    documents = {row["segment_id"]: row for row in view["segments"]}
    actions = {action["action_id"]: action for turn in view["turns"] for action in turn["actions"]}
    events = {event["event_id"]: event for event in view["events"]}
    spans = {}
    for span in resolved_mask["positive_content_spans"]:
        original_id = span["original_segment_id"]
        document = documents.get(original_id)
        start, end = span["start"], span["end"]
        if (
            document is None
            or document["kind"] != "public_content"
            or span.get("layer") != "reason"
            or type(start) is not int
            or type(end) is not int
            or not 0 <= start < end <= len(document["text"])
            or document["text"][start:end] != span["quote"]
        ):
            raise ValueError("positive content span is not original public text")
        spans.setdefault(original_id, []).append((start, end))
    positive_actions = set(resolved_mask["positive_action_ids"])
    if len(positive_actions) != len(resolved_mask["positive_action_ids"]):
        raise ValueError("duplicate positive action identity")
    for action_id in positive_actions:
        action = actions.get(action_id)
        event = events.get(action["event_id"]) if action else None
        if event is None or event["is_error"]:
            raise ValueError("positive action lacks an actual successful execution")
    token_hash, template_hash = tokenizer_binding(tokenizer)
    eos = tokenizer.eos_token_id
    if type(eos) is not int or eos < 0 or not getattr(tokenizer, "is_fast", False):
        raise ValueError("span supervision requires the real fast Student tokenizer and EOS")
    rows, failures = [], []
    for index, (turn, request, projected) in enumerate(
        zip(
            episode.turns,
            requests,
            view["turns"],
            strict=True,
        )
    ):
        prompt = tokenizer.apply_chat_template(
            _student_messages(request["messages"]),
            tools=request["tools"],
            tokenize=False,
            add_generation_prompt=True,
        )
        response = _native_response(turn)
        text = prompt + response
        encoded = tokenizer(
            text,
            add_special_tokens=False,
            truncation=False,
            padding=False,
            return_offsets_mapping=True,
        )
        ids = list(encoded["input_ids"])
        offsets = encoded["offset_mapping"]
        prompt_ids = tokenizer(prompt, add_special_tokens=False, truncation=False)["input_ids"]
        if ids[: len(prompt_ids)] != prompt_ids:
            raise ValueError("prompt boundary retokenizes; no repair is permitted")
        if (
            tokenizer.decode(ids, skip_special_tokens=False, clean_up_tokenization_spaces=False)
            != text
        ):
            raise ValueError("Student tokenizer does not preserve the full public representation")
        intervals = {"reason": [], "tool": [], "final": []}
        for start, end in spans.get(projected["public_content_segment_id"], []):
            intervals["reason"].append((len(prompt) + start, len(prompt) + end))
        action_layer = None
        cursor = len(turn.raw_text) + (1 if turn.raw_text and turn.tool_calls else 0)
        for action_index, (call, action) in enumerate(
            zip(turn.tool_calls, projected["actions"], strict=True)
        ):
            envelope = '<tool_call>\n{"name": ' + json.dumps(call.name, ensure_ascii=False)
            envelope += ', "arguments": ' + call.raw_arguments + "}\n</tool_call>"
            if response[cursor : cursor + len(envelope)] != envelope:
                raise ValueError("Student action envelope lost original argument bytes")
            if action["action_id"] in positive_actions:
                if len(turn.tool_calls) != 1:
                    raise ValueError("multiple tool responses cannot be positively targeted")
                action_layer = "final" if call.name == "submit_program" else "tool"
                intervals[action_layer].append(
                    (len(prompt) + cursor, len(prompt) + cursor + len(envelope))
                )
            cursor += len(envelope) + (1 if action_index + 1 < len(turn.tool_calls) else 0)
        layer_positions = {name: [] for name in intervals}
        for position, (start, end) in enumerate(offsets):
            if position < len(prompt_ids) or end <= start:
                continue
            for layer, ranges in intervals.items():
                if any(left <= start < end <= right for left, right in ranges):
                    layer_positions[layer].append(position)
        eos_position = len(ids)
        ids.append(eos)
        if action_layer is not None:
            layer_positions[action_layer].append(eos_position)
        targets = sorted(
            position for positions in layer_positions.values() for position in positions
        )
        if len(set(targets)) != len(targets) or any(position <= 0 for position in targets):
            raise ValueError("overlapping or causally invalid layer target positions")
        if len(ids) > context_limit:
            failures.append(
                {
                    "turn_index": index,
                    "reason": "untruncated_context_overflow",
                    "sequence_tokens": len(ids),
                    "context_limit": context_limit,
                }
            )
        body = {
            "turn_index": index,
            "api_response_id": turn.provider_metadata["api_response"]["id"],
            "public_request_sha256": digest(request),
            "raw_response_sha256": _sha(turn.raw_text),
            "rendered_prompt": prompt,
            "rendered_response": response,
            "input_ids": ids,
            "prompt_token_count": len(prompt_ids),
            "target_positions": targets,
            "target_ids": [ids[position] for position in targets],
            "layer_target_positions": layer_positions,
            "layer_target_counts": {layer: len(value) for layer, value in layer_positions.items()},
            "student_eos_appended": True,
            "student_eos_position": eos_position,
            "student_eos_supervised": action_layer is not None,
            "response_character_target_intervals": {
                layer: [[start - len(prompt), end - len(prompt)] for start, end in ranges]
                for layer, ranges in intervals.items()
            },
        }
        rows.append({**body, "row_sha256": digest(body)})
    total_targets = sum(len(row["target_ids"]) for row in rows)
    if total_targets == 0:
        failures.append({"reason": "no_review_approved_student_targets"})
    body = {
        "schema": "v6_student_encoding.v1",
        "task_id": episode.task_id,
        "episode_sha256": digest(episode),
        "view_id": view["view_id"],
        "resolved_mask_sha256": digest(resolved_mask),
        "tokenizer_digest": token_hash,
        "chat_template_digest": template_hash,
        "context_limit": context_limit,
        "context_truncated": False,
        "encoding_policy": ENCODING_POLICY,
        "eos_policy": EOS_POLICY,
        "encoding_origin": "offline_student_tokenizer_not_api_sampling",
        "api_original_sampling_tokens_claimed": False,
        "not_a_TokenReceipt": True,
        "semantic_qualification_not_decided_here": True,
        "encoding_admitted": not failures,
        "failures": failures,
        "rows": rows,
        "total_supervised_tokens": total_targets,
        "L_P": total_targets,
        "total_sequence_tokens": sum(len(row["input_ids"]) for row in rows),
        "max_sequence_tokens": max((len(row["input_ids"]) for row in rows), default=0),
        "layer_target_counts": {
            layer: sum(row["layer_target_counts"][layer] for row in rows)
            for layer in ("reason", "tool", "final")
        },
        "layer_normalization": "none; all five arms use q/(batch_size*whole_package_L_P)",
    }
    return {**body, "encoding_id": "v6_student_encoding:" + digest(body)}
