"""Original-request supervision candidates and tokenizer-only representation checks.

Eligibility comes from the independent online qualification and its complete
HTTP-to-Submission bindings, never from a callback's self-declared origin.  This
module does not execute a task, call a Provider, load Student weights, assign a
quotient class, or compute a training loss.
"""

from __future__ import annotations

import copy
from pathlib import Path
from typing import Any

from trusted_synthesis.canonical_json import canonical_json_bytes
from trusted_synthesis.domains.finance.qa_vnext.protocol import (
    contract,
    parse,
)
from trusted_synthesis.domains.finance.qa_vnext.protocol import (
    record as public_record,
)
from trusted_synthesis.experiments.qa_reasoning_share_training_preflight import (
    tokenization as frozen_tokenizer_assets,
)

from .models import identity, read_json, record, require, sha

MAXIMUM_SEQUENCE_LENGTH = 24_576
REPRESENTATION_VERSION = "finance_qa_vnext_original_request_response_candidates.v1"
TURN_IDS = (
    "public_request_id",
    "public_runtime_state_id",
    "provider_attempt_id",
    "request_id",
    "response_id",
    "submission_id",
    "receipt_id",
    "model_origin_evidence_id",
)
ROW_IDS = (
    "task_id",
    "context_id",
    "protocol_id",
    "session_id",
    "public_runtime_state_id",
    "model_origin_evidence_id",
    "provider_attempt_id",
    "public_request_id",
    "request_id",
    "response_id",
    "submission_id",
    "receipt_id",
    "qualification_id",
)


def _equal(left: Any, right: Any) -> bool:
    return canonical_json_bytes(left) == canonical_json_bytes(right)


def _public_identity(value: dict[str, Any], kind: str) -> None:
    expected = public_record(
        kind, **{key: item for key, item in value.items() if key not in {"id", "schema_version"}}
    )
    require(_equal(value, expected), "representation.public_identity." + kind)


def _string_fields(value: dict[str, Any], names: tuple[str, ...], code: str) -> None:
    require(all(isinstance(value.get(name), str) and value[name] for name in names), code)


def _bound_bytes(directory: Path, turn: dict[str, Any], prefix: str) -> bytes:
    name, digest = turn.get(prefix + "_path"), turn.get(prefix + "_sha256")
    require(isinstance(name, str) and bool(name), "representation.bound_path")
    assert isinstance(name, str)
    require(isinstance(digest, str) and len(digest) == 64, "representation.bound_digest")
    relative = Path(name)
    require(
        not relative.is_absolute() and ".." not in relative.parts and relative.as_posix() == name,
        "representation.relative_path",
    )
    base = directory.resolve()
    target = base / relative
    require(
        target.is_file() and not target.is_symlink() and target.resolve().is_relative_to(base),
        "representation.bound_file",
    )
    data = target.read_bytes()
    require(sha(data) == digest, "representation.bound_bytes." + prefix)
    return data


def _messages(value: Any) -> list[dict[str, str]]:
    require(
        isinstance(value, list)
        and len(value) == 2
        and all(
            isinstance(message, dict)
            and set(message) == {"role", "content"}
            and isinstance(message["content"], str)
            for message in value
        )
        and [message["role"] for message in value] == ["system", "user"],
        "representation.original_messages",
    )
    return copy.deepcopy(value)


def _session_binding(session: dict[str, Any], qualification: dict[str, Any]) -> None:
    _public_identity(session, "session")
    require(session.get("protocol_id") == contract()["id"], "representation.new_public_protocol")
    require(
        session["id"] == qualification.get("session_id")
        and session["context_id"] == qualification.get("context_id")
        and session["protocol_id"] == qualification.get("protocol_id"),
        "representation.qualification_session_binding",
    )


def _qualified_domain_audit(session: dict[str, Any], qualification: dict[str, Any]) -> None:
    audit = qualification.get("domain_audit")
    require(isinstance(audit, dict), "representation.independent_domain_audit")
    assert isinstance(audit, dict)
    _public_identity(audit, "session_audit")
    require(
        all(
            audit.get(field) is True
            for field in (
                "validation_passed",
                "evidence_complete",
                "qualified",
                "qa_valid",
                "trajectory_valid",
            )
        )
        and audit.get("errors") == []
        and audit.get("session_id") == session["id"]
        and audit.get("context_id") == session["context_id"]
        and audit.get("protocol_id") == session["protocol_id"]
        and audit.get("task_id") == qualification.get("task_id"),
        "representation.qualified_domain_audit",
    )
    expected_projection = (
        "supported" if audit.get("projection_supported") is True else "undetermined"
    )
    require(
        qualification.get("projection_status") == expected_projection,
        "representation.projection_status",
    )
    require(
        session.get("final") is not None
        and session["final"].get("qa_validation", {}).get("qa_valid") is True,
        "representation.qualified_final",
    )


def _original_turn(
    session: dict[str, Any], event: dict[str, Any], turn: dict[str, Any], directory: Path
) -> tuple[list[dict[str, str]], str]:
    _string_fields(turn, TURN_IDS, "representation.complete_turn_ids")
    require(
        type(turn.get("turn_index")) is int and turn["turn_index"] == event["sequence"],
        "representation.turn_index",
    )
    request, submission, receipt = event["request"], event["submission"], event["receipt"]
    for value, kind in ((request, "request"), (submission, "submission"), (receipt, "receipt")):
        _public_identity(value, kind)
    require(
        request["protocol_id"] == session["protocol_id"]
        and request["state"]["protocol_id"] == session["protocol_id"]
        and request["context"]["id"] == session["context_id"]
        and request["state"]["context_id"] == session["context_id"],
        "representation.public_request_context",
    )
    require(
        turn["public_request_id"]
        == request["id"]
        == submission["request_id"]
        == receipt["request_id"]
        and turn["public_runtime_state_id"] == request["state"]["id"] == receipt["state_id"]
        and turn["submission_id"] == submission["id"] == receipt["submission_id"]
        and turn["receipt_id"] == receipt["id"]
        and type(turn.get("admitted")) is bool
        and turn["admitted"] is receipt["admitted"],
        "representation.turn_parent_binding",
    )
    require(
        submission.get("host_repairs") == [] and receipt.get("no_host_semantic_repair") is True,
        "representation.no_host_repair",
    )
    original_request = _bound_bytes(directory, turn, "public_request")
    require(
        original_request == canonical_json_bytes(request), "representation.original_public_request"
    )
    request_bytes = _bound_bytes(directory, turn, "request")
    response_bytes = _bound_bytes(directory, turn, "response")
    raw_content = _bound_bytes(directory, turn, "raw_public_content")
    http_request, http_response = read_json(request_bytes), read_json(response_bytes)
    require(
        isinstance(http_request, dict) and isinstance(http_response, dict),
        "representation.http_objects",
    )
    messages = _messages(http_request.get("messages"))
    require(
        messages[-1]["content"].encode("utf-8") == original_request,
        "representation.actual_request_not_future_state",
    )
    choices = http_response.get("choices")
    require(
        isinstance(choices, list)
        and len(choices) == 1
        and isinstance(choices[0], dict)
        and isinstance(choices[0].get("message"), dict),
        "representation.original_public_response",
    )
    message = choices[0]["message"]
    target = message.get("content")
    require(
        message.get("role") == "assistant" and isinstance(target, str),
        "representation.original_public_content",
    )
    require(
        target.encode("utf-8") == raw_content
        and submission["raw_sha256"] == sha(raw_content)
        and submission["raw_bytes"] == len(raw_content),
        "representation.exact_original_target",
    )
    if "provider_response_id" in turn:
        require(
            http_response.get("id") == turn["provider_response_id"],
            "representation.provider_response_id",
        )
    if receipt["admitted"] is True:
        parsed = parse(raw_content)
        require(
            parsed["state_id"] == request["state"]["id"]
            and parsed["kind"] in {"action", "update", "final"}
            and _equal(parsed, event.get("parsed")),
            "representation.actual_admitted_submission",
        )
    return messages, target


def export_candidates(
    session: dict[str, Any] | None,
    qualification: dict[str, Any],
    transport_directory: Path,
) -> dict[str, Any]:
    """Export every admitted turn of one independently qualified model session.

    Failed, unknown, not-started, and non-model sessions return zero candidate
    rows.  Qualified sessions with an unsupported quotient projection remain
    eligible; this round does not materialize any quotient Assignment.
    """
    identity(qualification, "qualification")
    if session is not None:
        _session_binding(session, qualification)
    reasons = []
    if qualification.get("model_origin_verified") is not True:
        reasons.append("model_origin_not_independently_verified")
    if qualification.get("qualified") is not True:
        reasons.append("session_not_qualified")
    if qualification.get("evidence_complete") is not True:
        reasons.append("evidence_incomplete")
    if qualification.get("export_eligible") is not True:
        reasons.append("independent_qualification_did_not_admit_export")
    if session is not None and session.get("callback_binding", {}).get("origin") == "fixture":
        reasons.append("fixture_session")
    rows, excluded = [], []
    if not reasons:
        require(session is not None, "representation.qualified_session_missing")
        assert session is not None
        require(
            qualification.get("status") == "success"
            and qualification.get("qa_valid") is True
            and qualification.get("trajectory_valid") is True,
            "representation.qualified_status",
        )
        _qualified_domain_audit(session, qualification)
        _string_fields(
            qualification,
            (
                "task_id",
                "registered_session_id",
                "registration_id",
                "transport_manifest_id",
                "transport_manifest_sha256",
                "transport_ledger_id",
                "transport_binding_id",
                "model_configuration_id",
            ),
            "representation.complete_qualification_ids",
        )
        manifest_path = transport_directory / "manifest.json"
        require(not manifest_path.is_symlink(), "representation.manifest_symlink")
        manifest_raw = manifest_path.read_bytes()
        require(
            sha(manifest_raw) == qualification["transport_manifest_sha256"]
            and read_json(manifest_raw)["id"] == qualification["transport_manifest_id"],
            "representation.qualified_transport_manifest",
        )
        events, turns = session.get("events"), qualification.get("verified_turns")
        require(
            isinstance(events, list) and bool(events) and isinstance(turns, list),
            "representation.verified_turns",
        )
        assert isinstance(events, list) and isinstance(turns, list)
        require(
            all(isinstance(turn, dict) and type(turn.get("turn_index")) is int for turn in turns)
            and len(turns) == len(events)
            and {turn["turn_index"] for turn in turns} == set(range(len(events)))
            and [event.get("sequence") for event in events] == list(range(len(events))),
            "representation.exhaustive_turn_binding",
        )
        by_index = {turn["turn_index"]: turn for turn in turns}
        for event in events:
            turn = by_index[event["sequence"]]
            messages, target = _original_turn(session, event, turn, transport_directory)
            if event["receipt"]["admitted"] is not True:
                excluded.append(
                    {
                        "turn_index": event["sequence"],
                        "submission_id": event["submission"]["id"],
                        "receipt_id": event["receipt"]["id"],
                        "reason": "submission_not_admitted",
                        "original_transport_bytes_retained": True,
                    }
                )
                continue
            require(
                event["request"]["context"]["task_id"] == qualification["task_id"],
                "representation.task_binding",
            )
            rows.append(
                record(
                    "supervision_candidate",
                    representation_version=REPRESENTATION_VERSION,
                    task_id=qualification["task_id"],
                    context_id=session["context_id"],
                    protocol_id=session["protocol_id"],
                    session_id=session["id"],
                    registered_session_id=qualification["registered_session_id"],
                    registration_id=qualification["registration_id"],
                    provider_response_id=turn.get("provider_response_id"),
                    turn_index=event["sequence"],
                    **{name: turn[name] for name in TURN_IDS},
                    qualification_id=qualification["id"],
                    domain_audit_id=qualification["domain_audit"]["id"],
                    messages=messages,
                    target_text=target,
                    target_raw_sha256=sha(target.encode("utf-8")),
                    target_raw_byte_count=len(target.encode("utf-8")),
                    public_request_sha256=turn["public_request_sha256"],
                    http_request_sha256=turn["request_sha256"],
                    http_response_sha256=turn["response_sha256"],
                    submission_kind=event["parsed"]["kind"],
                    admitted=True,
                    model_origin_verified=True,
                    qualified=True,
                    original_request_feedback_and_state_preserved=True,
                    original_public_content_preserved=True,
                    projection_status=qualification["projection_status"],
                    quotient_assignment_id=None,
                    class_weights_assigned=False,
                    legacy_rows_or_state_assignments_reused=False,
                )
            )
    return record(
        "supervision_export",
        representation_version=REPRESENTATION_VERSION,
        session_id=session["id"] if session is not None else qualification.get("session_id"),
        qualification_id=qualification["id"],
        rows=rows,
        candidate_count=len(rows),
        excluded_submissions=excluded,
        excluded_submission_count=len(excluded),
        session_exclusion_reasons=reasons,
        quotient_assignments_materialized=0,
        class_weights_assigned=False,
        legacy_27_rows_imported=False,
        old_P_Q_probabilities_inherited=False,
        student_parameter_loads=0,
        student_forward_calls=0,
        student_parameter_updates=0,
    )


def register_tokenizer(repo_root: Path, directory: Path | None = None) -> dict[str, Any]:
    """Reuse only the frozen local five-file tokenizer/configuration asset binding."""
    return frozen_tokenizer_assets.register_tokenizer(repo_root, directory)


def _candidate(row: dict[str, Any]) -> None:
    identity(row, "supervision_candidate")
    _string_fields(row, ROW_IDS, "representation.candidate_ids")
    require(row["protocol_id"] == contract()["id"], "representation.new_public_protocol")
    require(
        row.get("representation_version") == REPRESENTATION_VERSION
        and row.get("admitted") is True
        and row.get("qualified") is True
        and row.get("model_origin_verified") is True
        and row.get("quotient_assignment_id") is None
        and row.get("class_weights_assigned") is False,
        "representation.candidate_contract",
    )
    _messages(row.get("messages"))
    target = row.get("target_text")
    require(isinstance(target, str) and bool(target), "representation.candidate_target")
    assert isinstance(target, str)
    require(
        row["target_raw_sha256"] == sha(target.encode("utf-8"))
        and row["target_raw_byte_count"] == len(target.encode("utf-8")),
        "representation.candidate_target_bytes",
    )


def _tokenize_candidate(
    row: dict[str, Any], binding: dict[str, Any], tokenizer: Any
) -> dict[str, Any]:
    """Historical 24,576 policy; binding, output identity and default stay unchanged."""
    return encode_original_candidate(
        row, binding, tokenizer, maximum_sequence_length=MAXIMUM_SEQUENCE_LENGTH
    )


def encode_original_candidate(
    row: dict[str, Any],
    binding: dict[str, Any],
    tokenizer: Any,
    *,
    maximum_sequence_length: int,
) -> dict[str, Any]:
    """Shared exact encoder; callers own a separately validated length policy.

    A larger cap is not a mutation of the historical tokenizer binding. New-policy
    callers must give their returned record a new condition-bound identity.
    """
    require(
        type(maximum_sequence_length) is int and maximum_sequence_length > 0,
        "representation.sequence_cap",
    )
    messages, target = row["messages"], row["target_text"]
    prefix = tokenizer.apply_chat_template(messages, tokenize=False, add_generation_prompt=True)
    full = tokenizer.apply_chat_template(
        [*messages, {"role": "assistant", "content": target}],
        tokenize=False,
        add_generation_prompt=False,
    )
    require(
        full == prefix + target + frozen_tokenizer_assets.CHAT_SUFFIX,
        "representation.rendered_content_changed",
    )
    start, end = len(prefix), len(prefix) + len(target)
    prefix_ids = tokenizer(prefix, add_special_tokens=False, truncation=False, padding=False)[
        "input_ids"
    ]
    encoded = tokenizer(
        full,
        add_special_tokens=False,
        truncation=False,
        padding=False,
        return_attention_mask=True,
        return_offsets_mapping=True,
    )
    ids, offsets = encoded["input_ids"], encoded["offset_mapping"]
    require(ids[: len(prefix_ids)] == prefix_ids, "representation.prefix_token_mismatch")
    require(
        len(offsets) == len(ids)
        and all(0 <= left <= right <= len(full) for left, right in offsets),
        "representation.offset_shape",
    )
    require(
        not any(left < start < right or left < end < right for left, right in offsets),
        "representation.boundary_crossing",
    )
    selected = [
        index for index, (left, right) in enumerate(offsets) if start <= left < right <= end
    ]
    require(bool(selected) and selected[0] > 0, "representation.no_causal_target")
    require(
        selected == list(range(len(prefix_ids), len(prefix_ids) + len(selected))),
        "representation.target_token_interval",
    )
    target_start, target_end = selected[0], selected[-1] + 1
    covered = start
    # Byte-fallback pieces can share one Unicode character's offsets. Exact
    # target decoding below disambiguates these overlaps without dropping bytes.
    for left, right in offsets[target_start:target_end]:
        require(
            left <= covered and start <= left < right <= end,
            "representation.target_offset_coverage",
        )
        covered = max(covered, right)
    require(covered == end, "representation.target_offset_coverage")
    target_ids = ids[target_start:target_end]
    require(
        not set(target_ids) & set(tokenizer.all_special_ids),
        "representation.special_token_inside_target",
    )
    decoded = tokenizer.decode(
        target_ids, skip_special_tokens=False, clean_up_tokenization_spaces=False
    )
    require(decoded.encode("utf-8") == target.encode("utf-8"), "representation.target_decode")
    require(
        ids[target_end:] == frozen_tokenizer_assets.SUFFIX_TOKEN_IDS, "representation.suffix_tokens"
    )
    require(encoded["attention_mask"] == [1] * len(ids), "representation.unexpected_padding")
    fits = len(ids) <= maximum_sequence_length
    mask = [int(target_start <= index < target_end) for index in range(len(ids))]
    labels = [token if mask[index] else -100 for index, token in enumerate(ids)]
    require(sum(mask[1:]) == len(selected) and mask[0] == 0, "representation.causal_shift")
    return record(
        "token_representation",
        row_id=row["id"],
        session_id=row["session_id"],
        task_id=row["task_id"],
        qualification_id=row["qualification_id"],
        public_runtime_state_id=row["public_runtime_state_id"],
        tokenizer_binding_id=binding["id"],
        tokenrepresentation_status="fit" if fits else "not_fit",
        reason=None if fits else "maximum_sequence_length_exceeded",
        consumable_token_representation=fits,
        maximum_sequence_length=maximum_sequence_length,
        sequence_length=len(ids),
        prompt_token_count=len(prefix_ids),
        target_token_count=len(target_ids),
        suffix_token_count=len(ids) - target_end,
        input_ids=ids if fits else None,
        attention_mask=encoded["attention_mask"] if fits else None,
        target_mask=mask if fits else None,
        labels=labels if fits else None,
        target_token_start=target_start,
        target_token_end=target_end,
        target_character_start=start,
        target_character_end=end,
        character_offsets_use_unicode_codepoints=True,
        causal_shift=1,
        causal_target_token_start=target_start - 1,
        causal_target_token_end=target_end - 1,
        rendered_sha256=sha(full.encode("utf-8")),
        rendered_byte_count=len(full.encode("utf-8")),
        target_raw_sha256=sha(target.encode("utf-8")),
        target_raw_byte_count=len(target.encode("utf-8")),
        truncated=False,
        raw_candidate_and_qualification_retained=True,
        quotient_assignment_id=None,
        class_weights_assigned=False,
        boundary_checks={
            "full_render_is_exact_prefix_content_suffix": True,
            "original_content_utf8_bytes_preserved": True,
            "full_token_prefix_equals_prompt_tokens": True,
            "no_token_crosses_content_boundaries": True,
            "content_offsets_cover_exact_character_interval": True,
            "content_tokens_decode_to_original_utf8_bytes": True,
            "content_token_interval_is_contiguous": True,
            "prompt_and_role_header_have_zero_target_mask": True,
            "eos_and_suffix_have_zero_target_mask": True,
            "padding_is_absent_before_collation": True,
            "all_target_positions_have_causal_predecessor": True,
            "no_truncation": True,
        },
    )


def tokenize_candidates(
    rows: list[dict[str, Any]], binding: dict[str, Any] | None = None
) -> dict[str, Any]:
    """Check new rows without old row eligibility, class weights, or truncation.

    Empty candidate sets do not load a tokenizer or fabricate a positive example.
    An overlength row remains a valid raw candidate, with a non-consumable token
    record; it is not relabeled as a failed model session.
    """
    require(isinstance(rows, list), "representation.candidate_list")
    for row in rows:
        _candidate(row)
    require(len({row["id"] for row in rows}) == len(rows), "representation.duplicate_candidates")
    records = []
    if rows:
        require(isinstance(binding, dict), "representation.tokenizer_binding_required")
        assert binding is not None
        require(
            binding.get("maximum_sequence_length") == MAXIMUM_SEQUENCE_LENGTH,
            "representation.fixed_sequence_cap",
        )
        tokenizer = frozen_tokenizer_assets.load_tokenizer(binding)
        records = [_tokenize_candidate(row, binding, tokenizer) for row in rows]
        require(
            tokenizer.chat_template == binding["chat_template"], "representation.template_runtime"
        )
        members, _ = frozen_tokenizer_assets._read_members(Path(binding["directory"]))
        require(members == binding["members"], "representation.tokenizer_changed_during_use")
    fit_count = sum(item["tokenrepresentation_status"] == "fit" for item in records)
    return record(
        "token_representation_dataset",
        representation_version=REPRESENTATION_VERSION,
        tokenizer_binding_id=binding["id"] if binding is not None else None,
        records=records,
        candidate_count=len(rows),
        fit_count=fit_count,
        not_fit_count=len(records) - fit_count,
        status="no_positive_candidates"
        if not rows
        else "all_fit"
        if fit_count == len(rows)
        else "contains_not_fit",
        positive_representation_validated=bool(records) and fit_count == len(rows),
        tokenizer_loaded=bool(rows),
        maximum_sequence_length=MAXIMUM_SEQUENCE_LENGTH,
        old_eligibility_or_rows_reused=False,
        class_weights_assigned=False,
        student_parameter_loads=0,
        student_forward_calls=0,
        student_parameter_updates=0,
        GPU_jobs=0,
    )
