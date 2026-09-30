"""State-independent lossless SFT encoding with same-authority token-set union.

Each approved character span is tested separately against original token offsets.
Only the resulting token positions are unioned. Neither character ranges, public
history nor supervision authorities are merged, expanded or selected by outcomes.
"""

from __future__ import annotations

import copy
import hashlib
import json

from .contracts import digest
from .encoding import _native_response, _student_messages
from .providers import tokenizer_binding
from .v6_encoding import CONTEXT_LIMIT, _api_requests
from .v6_task import public_trajectory_view

MANIFEST_SCHEMA = "v14_package_supervision.v1"
ENCODING_SCHEMA = "v14_student_encoding.v1"
ENCODING_POLICY = "v14_state_independent_original_span_union.v1"
TOKEN_SELECTION = "union_of_individually_bounded_original_spans"
EOS_POLICY = "student_eos_positive_iff_whole_action_positive.v1"
AUTHORITIES = {
    "V12_A_original",
    "V13_completion_only",
    "V14_derived_overlap",
    "V14_completion_only",
}


def _require(condition, message):
    if not condition:
        raise ValueError(message)


def _bound(body):
    return body | dict(id=digest(body))


def supervision_manifest(
    episode,
    *,
    slot_id,
    authority_record,
    projection,
    population_id,
    projection_authority,
):
    """Bind one previously settled authority; this function makes no semantic decision."""
    _require(
        projection_authority in AUTHORITIES, "explicit registered projection authority required"
    )
    _require(
        isinstance(projection, dict) and projection.get("usable", True) is True,
        "unresolved projection cannot become an encoding authority",
    )
    _require(
        isinstance(authority_record, dict) and set(authority_record) >= {"path", "sha256", "id"},
        "byte-bound original/derived authority reference required",
    )
    view = public_trajectory_view(episode, slot_id=slot_id)
    body = dict(
        schema=MANIFEST_SCHEMA,
        population_id=population_id,
        slot_id=slot_id,
        task_id=episode.task_id,
        episode_sha256=digest(episode),
        view_id=view["view_id"],
        projection_authority=projection_authority,
        authority_record=copy.deepcopy(authority_record),
        original_projection=copy.deepcopy(projection),
        projection_sha256=digest(projection),
        positive_content_spans=[
            dict(
                original_segment_id=s["segment_id"],
                layer="reason",
                start=s["start"],
                end=s["end"],
                quote=s["quote"],
            )
            for s in projection["positive_content"]
        ],
        positive_action_ids=[a["action_id"] for a in projection["positive_actions"]],
        token_selection=TOKEN_SELECTION,
        character_spans_merged=False,
        same_single_authority_for_all_positive_targets=True,
        state_independent=True,
        state_or_chi_used=False,
        original_process_judgments_unchanged=True,
    )
    manifest = _bound(body)
    validate_manifest(episode, manifest)
    return manifest


def validate_manifest(episode, manifest):
    _require(
        manifest.get("schema") == MANIFEST_SCHEMA
        and manifest.get("id") == digest({k: v for k, v in manifest.items() if k != "id"})
        and manifest.get("episode_sha256") == digest(episode)
        and manifest.get("task_id") == episode.task_id
        and manifest.get("projection_authority") in AUTHORITIES
        and manifest.get("population_id")
        and manifest.get("token_selection") == TOKEN_SELECTION
        and manifest.get("character_spans_merged") is False
        and manifest.get("state_independent") is True
        and manifest.get("state_or_chi_used") is False,
        "immutable original V14 state-independent supervision manifest required",
    )
    projection = manifest["original_projection"]
    _require(manifest["projection_sha256"] == digest(projection), "authority projection changed")
    _require(
        manifest["positive_content_spans"]
        == [
            dict(
                original_segment_id=s["segment_id"],
                layer="reason",
                start=s["start"],
                end=s["end"],
                quote=s["quote"],
            )
            for s in projection["positive_content"]
        ]
        and manifest["positive_action_ids"]
        == [a["action_id"] for a in projection["positive_actions"]],
        "targets differ from the exact original authority selections",
    )
    view = public_trajectory_view(episode, slot_id=manifest["slot_id"])
    _require(manifest["view_id"] == view["view_id"], "original public history/view changed")
    documents = {d["segment_id"]: d for d in view["segments"]}
    for span in manifest["positive_content_spans"]:
        doc = documents.get(span["original_segment_id"])
        left, right = span["start"], span["end"]
        _require(
            doc is not None
            and doc["kind"] == "public_content"
            and span["layer"] == "reason"
            and type(left) is int
            and type(right) is int
            and 0 <= left < right <= len(doc["text"])
            and doc["text"][left:right] == span["quote"],
            "positive reason span must quote its exact original public response",
        )
    actions = {a["action_id"]: a for t in view["turns"] for a in t["actions"]}
    events = {e["event_id"]: e for e in view["events"]}
    _require(
        len(set(manifest["positive_action_ids"])) == len(manifest["positive_action_ids"]),
        "duplicate positive actions are not a new semantic approval",
    )
    for action_id in manifest["positive_action_ids"]:
        action = actions.get(action_id)
        event = events.get(action["event_id"]) if action else None
        _require(
            event is not None and not event["is_error"],
            "positive action needs its original successful event",
        )
    return view


def token_position_union(offsets, ranges, *, prompt_token_count):
    """T_positive = union_j T(original span_j), not T(union_j character spans)."""
    selected = set()
    for approved_left, approved_right in ranges:
        selected.update(
            i
            for i, (left, right) in enumerate(offsets)
            if i >= prompt_token_count
            and right > left
            and approved_left <= left < right <= approved_right
        )
    return sorted(selected)


def encode_for_student(episode, manifest, tokenizer, *, context_limit=CONTEXT_LIMIT):
    _require(
        type(context_limit) is int and context_limit == CONTEXT_LIMIT,
        "registered context remains 24576, without truncation",
    )
    view = validate_manifest(episode, manifest)
    requests = _api_requests(episode, view)
    spans = {}
    for span in manifest["positive_content_spans"]:
        spans.setdefault(span["original_segment_id"], []).append((span["start"], span["end"]))
    positive_actions = set(manifest["positive_action_ids"])
    tokenizer_id, template_id = tokenizer_binding(tokenizer)
    eos = tokenizer.eos_token_id
    _require(
        type(eos) is int and eos >= 0 and getattr(tokenizer, "is_fast", False),
        "real fast Student tokenizer with EOS required",
    )
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
        _require(
            ids[: len(prompt_ids)] == prompt_ids, "prompt boundary retokenizes; no silent repair"
        )
        _require(
            tokenizer.decode(ids, skip_special_tokens=False, clean_up_tokenization_spaces=False)
            == text,
            "Student rendering must preserve complete original bytes",
        )
        intervals = dict(reason=[], tool=[], final=[])
        for left, right in spans.get(projected["public_content_segment_id"], []):
            intervals["reason"].append((len(prompt) + left, len(prompt) + right))
        eos_layer = None
        cursor = len(turn.raw_text) + int(bool(turn.raw_text and turn.tool_calls))
        for call_index, (call, action) in enumerate(
            zip(turn.tool_calls, projected["actions"], strict=True)
        ):
            envelope = '<tool_call>\n{"name": ' + json.dumps(call.name, ensure_ascii=False)
            envelope += ', "arguments": ' + call.raw_arguments + "}\n</tool_call>"
            _require(
                response[cursor : cursor + len(envelope)] == envelope,
                "Student tool envelope must retain original argument bytes",
            )
            if action["action_id"] in positive_actions:
                _require(
                    len(turn.tool_calls) == 1,
                    "positive multi-action response remains outside this encoding",
                )
                eos_layer = "final" if call.name == "submit_program" else "tool"
                intervals[eos_layer].append(
                    (len(prompt) + cursor, len(prompt) + cursor + len(envelope))
                )
            cursor += len(envelope) + int(call_index + 1 < len(turn.tool_calls))
        positions = {
            layer: token_position_union(
                encoded["offset_mapping"], ranges, prompt_token_count=len(prompt_ids)
            )
            for layer, ranges in intervals.items()
        }
        eos_position = len(ids)
        ids.append(eos)
        if eos_layer is not None:
            positions[eos_layer].append(eos_position)
        targets = sorted(p for values in positions.values() for p in values)
        _require(
            len(set(targets)) == len(targets) and all(p > 0 for p in targets),
            "target layers must remain disjoint and causal; no repeated loss",
        )
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
            target_ids=[ids[p] for p in targets],
            layer_target_positions=positions,
            layer_target_counts={layer: len(values) for layer, values in positions.items()},
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
        schema=ENCODING_SCHEMA,
        slot_id=manifest["slot_id"],
        task_id=episode.task_id,
        episode_sha256=digest(episode),
        view_id=view["view_id"],
        supervision_manifest_sha256=digest(manifest),
        authority_record=manifest["authority_record"],
        population_id=manifest["population_id"],
        tokenizer_digest=tokenizer_id,
        chat_template_digest=template_id,
        context_limit=context_limit,
        context_truncated=False,
        original_history_retained=True,
        encoding_policy=ENCODING_POLICY,
        token_selection=TOKEN_SELECTION,
        eos_policy=EOS_POLICY,
        state_independent=True,
        state_or_chi_used=False,
        character_spans_merged=False,
        encoding_origin="offline_student_tokenizer_not_api_sampling",
        api_original_sampling_tokens_claimed=False,
        not_a_TokenReceipt=True,
        feedback_requires_actual_local_tokens_and_EOS=True,
        semantic_qualification_not_decided_here=True,
        training_authorized=False,
        encoding_admitted=not failures,
        encoding_started=True,
        failures=failures,
        rows=rows,
        total_supervised_tokens=count,
        L_P=count,
        total_sequence_tokens=sum(len(row["input_ids"]) for row in rows),
        max_sequence_tokens=max((len(row["input_ids"]) for row in rows), default=0),
        layer_target_counts=layers,
        public_content_present=any(t.raw_text.strip() for t in episode.turns),
        public_content_without_positive_reason_targets=any(
            t.raw_text.strip() for t in episode.turns
        )
        and layers["reason"] == 0,
        substantive_reasoning_quality="not_inferred_from_tags_or_token_counts",
        layer_normalization="none; all five arms use pi/(actual_batch_size*n_xz*whole_package_L_P)",
    )
    return body | dict(encoding_id="v14_student_encoding:" + digest(body))


def validate_encoding(encoding, episode, manifest, tokenizer):
    _require(
        encoding == encode_for_student(episode, manifest, tokenizer),
        "cached V14 encoding differs from original source, authority or tokenizer",
    )
    return encoding
