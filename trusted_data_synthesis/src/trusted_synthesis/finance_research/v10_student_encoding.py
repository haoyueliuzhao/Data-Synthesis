"""Offline Student encoding from one V10 supervision authority, not a proof graph.

Original public history is retained even when a response has no positive target.
The output is SFT material only; it cannot replace local feedback TokenReceipts.
"""

from __future__ import annotations

import hashlib
import json

from .contracts import Episode, digest
from .encoding import _native_response, _student_messages
from .providers import tokenizer_binding
from .v6_encoding import CONTEXT_LIMIT, _api_requests
from .v6_task import public_trajectory_view

ENCODING_POLICY = "v10_single_authority_original_spans.v1"
EOS_POLICY = "student_eos_positive_iff_whole_action_positive.v1"


def encode_process_review_for_student(
    episode: Episode,
    manifest: dict,
    tokenizer,
    *,
    context_limit: int = CONTEXT_LIMIT,
) -> dict:
    """Preserve all turns and actual observations; supervise only explicit spans.

    There is no assertion that reviewers used identical labels or that a complete
    proof graph exists. Zero reason targets are reported, never repaired by dropping
    public text or inventing new explanation. Encoding is not permission to train.
    """
    from .v10_process_review import validate_manifest

    if type(context_limit) is not int or context_limit != CONTEXT_LIMIT:
        raise ValueError("registered Student context is 24576; no silent length variant")
    validate_manifest(episode, manifest)
    view = public_trajectory_view(episode, slot_id=manifest.get("slot_id"))
    # This helper checks actual API inputs/returns/history, not V8 review labels.
    requests = _api_requests(episode, view)
    documents = {item["segment_id"]: item for item in view["segments"]}
    actions = {item["action_id"]: item for turn in view["turns"] for item in turn["actions"]}
    events = {item["event_id"]: item for item in view["events"]}
    positive_actions = set(manifest["positive_action_ids"])
    if len(positive_actions) != len(manifest["positive_action_ids"]):
        raise ValueError("duplicate positive action")
    for action_id in positive_actions:
        action = actions.get(action_id)
        event = events.get(action["event_id"]) if action else None
        if event is None or event["is_error"]:
            raise ValueError("positive action requires its actual successful execution")
    spans = {}
    for span in manifest["positive_content_spans"]:
        doc = documents.get(span["original_segment_id"])
        left, right = span["start"], span["end"]
        if (
            doc is None
            or doc["kind"] != "public_content"
            or span.get("layer") != "reason"
            or type(left) is not int
            or type(right) is not int
            or not 0 <= left < right <= len(doc["text"])
            or doc["text"][left:right] != span["quote"]
        ):
            raise ValueError("positive content must quote the original public response")
        ranges = spans.setdefault(doc["segment_id"], [])
        if any(left < b and a < right for a, b in ranges):
            raise ValueError("overlapping positive content spans")
        ranges.append((left, right))

    tokenizer_id, template_id = tokenizer_binding(tokenizer)
    eos = tokenizer.eos_token_id
    if type(eos) is not int or eos < 0 or not getattr(tokenizer, "is_fast", False):
        raise ValueError("a real fast Student tokenizer with EOS is required")
    rows, failures = [], []
    for index, (turn, request, projected) in enumerate(
        zip(episode.turns, requests, view["turns"], strict=True)
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
        prompt_ids = tokenizer(prompt, add_special_tokens=False, truncation=False)["input_ids"]
        if ids[: len(prompt_ids)] != prompt_ids:
            raise ValueError("prompt boundary retokenizes; no silent repair")
        if (
            tokenizer.decode(ids, skip_special_tokens=False, clean_up_tokenization_spaces=False)
            != text
        ):
            raise ValueError("Student rendering is not a lossless original representation")
        intervals = {"reason": [], "tool": [], "final": []}
        for left, right in spans.get(projected["public_content_segment_id"], []):
            intervals["reason"].append((len(prompt) + left, len(prompt) + right))
        eos_layer = None
        cursor = len(turn.raw_text) + int(bool(turn.raw_text and turn.tool_calls))
        for call_index, (call, action) in enumerate(
            zip(turn.tool_calls, projected["actions"], strict=True)
        ):
            envelope = '<tool_call>\n{"name": ' + json.dumps(call.name, ensure_ascii=False)
            envelope += ', "arguments": ' + call.raw_arguments + "}\n</tool_call>"
            if response[cursor : cursor + len(envelope)] != envelope:
                raise ValueError("Student tool envelope altered original argument bytes")
            if action["action_id"] in positive_actions:
                if len(turn.tool_calls) != 1:
                    raise ValueError("positive multi-action response is outside this encoding")
                eos_layer = "final" if call.name == "submit_program" else "tool"
                intervals[eos_layer].append(
                    (len(prompt) + cursor, len(prompt) + cursor + len(envelope))
                )
            cursor += len(envelope) + int(call_index + 1 < len(turn.tool_calls))
        positions = {layer: [] for layer in intervals}
        for position, (left, right) in enumerate(encoded["offset_mapping"]):
            if position < len(prompt_ids) or right <= left:
                continue
            for layer, ranges in intervals.items():
                if any(a <= left < right <= b for a, b in ranges):
                    positions[layer].append(position)
        eos_position = len(ids)
        ids.append(eos)
        if eos_layer is not None:
            positions[eos_layer].append(eos_position)
        targets = sorted(position for items in positions.values() for position in items)
        if len(set(targets)) != len(targets) or any(position <= 0 for position in targets):
            raise ValueError("overlapping or noncausal targets")
        if len(ids) > context_limit:
            failures.append(
                dict(
                    turn_index=index,
                    reason="untruncated_context_overflow",
                    sequence_tokens=len(ids),
                    context_limit=context_limit,
                )
            )
        row = dict(
            turn_index=index,
            api_response_id=turn.provider_metadata["api_response"]["id"],
            public_request_sha256=digest(request),
            raw_response_sha256=hashlib.sha256(turn.raw_text.encode()).hexdigest(),
            rendered_prompt=prompt,
            rendered_response=response,
            input_ids=ids,
            prompt_token_count=len(prompt_ids),
            target_positions=targets,
            target_ids=[ids[position] for position in targets],
            layer_target_positions=positions,
            layer_target_counts={layer: len(items) for layer, items in positions.items()},
            student_eos_appended=True,
            student_eos_position=eos_position,
            student_eos_supervised=eos_layer is not None,
            response_character_target_intervals={
                layer: [[a - len(prompt), b - len(prompt)] for a, b in ranges]
                for layer, ranges in intervals.items()
            },
        )
        rows.append(row | dict(row_sha256=digest(row)))
    count = sum(len(row["target_ids"]) for row in rows)
    if not count:
        failures.append(dict(reason="no_explicit_review_approved_targets"))
    layers = {
        layer: sum(row["layer_target_counts"][layer] for row in rows)
        for layer in ("reason", "tool", "final")
    }
    body = dict(
        schema="v10_student_encoding.v1",
        task_id=episode.task_id,
        episode_sha256=digest(episode),
        view_id=view["view_id"],
        supervision_manifest_sha256=digest(manifest),
        tokenizer_digest=tokenizer_id,
        chat_template_digest=template_id,
        context_limit=context_limit,
        context_truncated=False,
        original_history_retained=True,
        encoding_policy=ENCODING_POLICY,
        eos_policy=EOS_POLICY,
        encoding_origin="offline_student_tokenizer_not_api_sampling",
        api_original_sampling_tokens_claimed=False,
        not_a_TokenReceipt=True,
        feedback_requires_actual_local_tokens_and_EOS=True,
        semantic_qualification_not_decided_here=True,
        training_authorized=False,
        encoding_admitted=not failures,
        failures=failures,
        rows=rows,
        total_supervised_tokens=count,
        L_P=count,
        total_sequence_tokens=sum(len(row["input_ids"]) for row in rows),
        max_sequence_tokens=max((len(row["input_ids"]) for row in rows), default=0),
        layer_target_counts=layers,
        public_content_present=any(turn.raw_text.strip() for turn in episode.turns),
        public_content_without_positive_reason_targets=(
            any(turn.raw_text.strip() for turn in episode.turns) and layers["reason"] == 0
        ),
        substantive_reasoning_quality="not_inferred_from_tags_or_token_counts",
        layer_normalization="none; all five arms use q/(batch_size*whole_package_L_P)",
    )
    return body | dict(encoding_id="v10_student_encoding:" + digest(body))
