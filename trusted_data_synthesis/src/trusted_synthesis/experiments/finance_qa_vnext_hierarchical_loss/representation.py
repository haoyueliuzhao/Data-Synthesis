"""Loss-only sidecars over byte-identical, already encoded public responses.

No tokenizer, model, file, private trace, or source is loaded here. Token/text
alignment authority is the original content-addressed encoder record; this
module rechecks that record's public candidate and exact stored target interval,
not a second tokenization. The containing material/catalog remains responsible
for admitting the original package bytes. Unknown mappings block the package.
"""

import copy

from trusted_synthesis.domains.finance.qa_vnext.protocol import parse as parse_public

from ..finance_qa_vnext_basis_student.kernel import validate_row
from ..finance_qa_vnext_eval_readiness import training_runtime
from ..finance_qa_vnext_model_execution import representation as original
from ..finance_qa_vnext_model_execution.models import identity as original_identity
from ..qa_reasoning_share_training_preflight.tokenization import SUFFIX_TOKEN_IDS
from .protocol import LAYERS, PROFILES, checked_record, encode, record, require, sha

TEACHER_AUTHORITY = "eval_readiness.v2.original_Teacher_response.public_content"
EXPORT_AUTHORITY = "model_execution.v1.supervision_candidate.public_content"
SYNTHETIC_AUTHORITY = "synthetic_CPU_control"
ANNOTATION_KIND = "package_layer_annotation"
BOUNDARY_FLAGS = {
    "full_render_is_exact_prefix_content_suffix",
    "original_content_utf8_bytes_preserved",
    "full_token_prefix_equals_prompt_tokens",
    "no_token_crosses_content_boundaries",
    "content_offsets_cover_exact_character_interval",
    "content_tokens_decode_to_original_utf8_bytes",
    "content_token_interval_is_contiguous",
    "prompt_and_role_header_have_zero_target_mask",
    "eos_and_suffix_have_zero_target_mask",
    "padding_is_absent_before_collation",
    "all_target_positions_have_causal_predecessor",
    "no_truncation",
}


def _original_identity(value, kind):
    expected = training_runtime.record(
        kind, **{key: item for key, item in value.items() if key not in {"id", "schema_version"}}
    )
    require(value == expected, "layers.original_Teacher_content_identity")


def _package(package):
    require(isinstance(package, dict), "layers.original_package_object")
    identifier = package.get("package_id", package.get("id"))
    require(isinstance(identifier, str) and identifier, "layers.original_package_identity")
    if "id" in package:
        _original_identity(package, "encoded_original_package")
        require(
            package.get("consumable") is True
            and package.get("errors") == []
            and package.get("truncation") is False,
            "layers.complete_consumable_original_package",
        )
    rows = package.get("rows")
    require(isinstance(rows, list) and rows, "layers.no_empty_or_dropped_package")
    require(
        all(isinstance(row, dict) and isinstance(row.get("candidate_id"), str) for row in rows)
        and len({row["candidate_id"] for row in rows}) == len(rows),
        "layers.unique_original_candidate_rows",
    )
    representations = [validate_row(row) for row in rows]
    total = sum(row["target_token_count"] for row in representations)
    require(
        type(package.get("whole_package_target_tokens")) is int
        and package["whole_package_target_tokens"] == total > 0,
        "layers.original_whole_package_denominator",
    )
    return identifier, rows


def _candidate(candidate):
    require(isinstance(candidate, dict), "layers.public_candidate_object")
    require(
        not {"reasoning_content", "private_reasoning", "private_reasoning_content"}
        & set(candidate),
        "layers.no_private_reasoning_candidate_field",
    )
    schema = candidate.get("schema_version")
    if schema == "eval_readiness.v2.original_Teacher_response":
        _original_identity(candidate, "original_Teacher_response")
        require(
            candidate.get("origin") == "live_teacher_callback"
            and candidate.get("training_sample") is False,
            "layers.original_live_Teacher_public_candidate",
        )
        parsed = training_runtime.primitive.strict_json(candidate["target_text"])
        require(isinstance(parsed, dict), "layers.original_Teacher_response_object")
        # Exact dispatch of the original training runtime. A public Final's
        # explanations/citations/other public fields remain in Final as a whole.
        if "final" in parsed:
            require(candidate.get("response_kind") == "Final", "layers.Final_metadata_matches_raw")
            kind, layer = "final", "final"
        else:
            require(
                set(parsed) == {"tool", "arguments"}
                and isinstance(parsed["tool"], str)
                and parsed["tool"]
                and isinstance(parsed["arguments"], dict)
                and candidate.get("response_kind") == parsed["tool"],
                "layers.tool_metadata_matches_original_raw",
            )
            kind, layer = "action", "tools"
        require(
            candidate.get("public_runtime_state_id")
            == "history:" + sha(encode(candidate.get("messages"))),
            "layers.original_public_history_identity",
        )
        authority, index = TEACHER_AUTHORITY, candidate.get("response_index")
    elif schema == "qa_vnext_model_execution_supervision_candidate.v1":
        original._candidate(candidate)
        require(
            candidate.get("original_public_content_preserved") is True
            and candidate.get("original_request_feedback_and_state_preserved") is True,
            "layers.original_public_export_contract",
        )
        parsed = parse_public(candidate["target_text"].encode("utf-8"))
        require(
            parsed["kind"] == candidate.get("submission_kind")
            and parsed["state_id"] == candidate.get("public_runtime_state_id"),
            "layers.public_submission_metadata_matches_raw",
        )
        kind = parsed["kind"]
        layer = "final" if kind == "final" else "tools"
        authority, index = EXPORT_AUTHORITY, candidate.get("turn_index")
    else:
        raise ValueError("layers.unknown_public_source_authority_blocks_package")
    require(type(index) is int and index >= 0, "layers.original_response_time_index")
    target = candidate.get("target_text")
    require(isinstance(target, str) and target, "layers.original_public_target_text")
    raw = target.encode("utf-8")
    require(candidate.get("target_raw_sha256") == sha(raw), "layers.original_target_raw_SHA")
    if "target_raw_byte_count" in candidate:
        require(candidate["target_raw_byte_count"] == len(raw), "layers.original_target_byte_count")
    messages = candidate.get("messages")
    require(
        isinstance(messages, list)
        and messages
        and all(
            isinstance(message, dict)
            and set(message) == {"role", "content"}
            and message["role"] in {"system", "user", "assistant", "tool"}
            and isinstance(message["content"], str)
            for message in messages
        ),
        "layers.original_public_message_history",
    )
    return authority, index, kind, layer


def _bound_representation(row, candidate):
    encoded = validate_row(row)
    original_identity(encoded, "token_representation")
    require(
        all(
            type(encoded.get(key)) is int
            for key in (
                "sequence_length",
                "prompt_token_count",
                "target_token_count",
                "suffix_token_count",
                "target_token_start",
                "target_token_end",
                "target_character_start",
                "target_character_end",
                "causal_shift",
                "causal_target_token_start",
                "causal_target_token_end",
                "target_raw_byte_count",
                "maximum_sequence_length",
            )
        ),
        "layers.original_integer_token_character_boundaries",
    )
    require(
        row["candidate_id"] == candidate["id"] == encoded["row_id"]
        and all(
            encoded[key] == candidate[key]
            for key in ("task_id", "session_id", "qualification_id", "public_runtime_state_id")
        ),
        "layers.original_candidate_and_encoded_row_join",
    )
    require(
        encoded["target_raw_sha256"] == candidate["target_raw_sha256"]
        and encoded["target_raw_byte_count"] == len(candidate["target_text"].encode("utf-8")),
        "layers.encoded_original_public_target_binding",
    )
    start, end, length = (
        encoded["target_token_start"],
        encoded["target_token_end"],
        encoded["sequence_length"],
    )
    require(
        type(start) is type(end) is int
        and 0 < start < end <= length
        and encoded["prompt_token_count"] == start
        and encoded["target_token_count"] == end - start
        and encoded["target_mask"] == [int(start <= i < end) for i in range(length)]
        and encoded["suffix_token_count"] == length - end == len(SUFFIX_TOKEN_IDS)
        and encoded["input_ids"][end:] == SUFFIX_TOKEN_IDS
        and encoded["causal_shift"] == 1
        and encoded["causal_target_token_start"] == start - 1
        and encoded["causal_target_token_end"] == end - 1,
        "layers.original_target_interval_context_suffix_and_causal_shift",
    )
    require(
        type(encoded["target_character_start"]) is int
        and encoded["target_character_start"] >= 0
        and encoded["target_character_end"] - encoded["target_character_start"]
        == len(candidate["target_text"])
        and encoded["character_offsets_use_unicode_codepoints"] is True
        and encoded["tokenrepresentation_status"] == "fit"
        and encoded["consumable_token_representation"] is True
        and encoded["truncated"] is False
        and encoded["raw_candidate_and_qualification_retained"] is True
        and encoded["maximum_sequence_length"] == 24576
        and encoded["attention_mask"] == [1] * length
        and isinstance(encoded.get("tokenizer_binding_id"), str)
        and encoded["tokenizer_binding_id"],
        "layers.original_encoder_no_truncation_or_retokenization",
    )
    flags = encoded.get("boundary_checks")
    require(
        isinstance(flags, dict)
        and set(flags) == BOUNDARY_FLAGS
        and all(value is True for value in flags.values()),
        "layers.original_encoder_boundary_checks_retained",
    )
    return encoded


def _masks(original_mask, layer):
    return {
        name: list(original_mask) if name == layer else [0] * len(original_mask) for name in LAYERS
    }


def _partition(rows, annotations, profile):
    require(profile in PROFILES, "layers.registered_availability_profile")
    require(len(rows) == len(annotations), "layers.all_original_rows_retained")
    counts = dict.fromkeys(LAYERS, 0)
    for row, annotated in zip(rows, annotations, strict=True):
        mask, layers = row["representation"]["target_mask"], annotated["layer_masks"]
        require(
            isinstance(layers, dict) and set(layers) == set(LAYERS), "layers.exact_three_layers"
        )
        require(
            all(
                isinstance(values, list)
                and len(values) == len(mask)
                and all(type(value) is int and value in (0, 1) for value in values)
                for values in layers.values()
            )
            and all(
                sum(layers[name][i] for name in LAYERS) == active for i, active in enumerate(mask)
            ),
            "layers.exact_once_target_partition_zero_context_suffix",
        )
        for name in LAYERS:
            counts[name] += sum(layers[name])
    require(
        counts["tools"] > 0
        and counts["final"] > 0
        and (counts["reasoning"] > 0 if profile == "public_rtf" else counts["reasoning"] == 0),
        "layers.missing_required_layer_blocks_whole_common_kernel",
    )
    return counts


def _annotation(package, candidates):
    identifier, rows = _package(package)
    require(
        isinstance(candidates, list) and all(isinstance(item, dict) for item in candidates),
        "layers.original_candidate_list",
    )
    require(
        [row["candidate_id"] for row in rows] == [item.get("id") for item in candidates],
        "layers.exact_original_candidates_no_reorder_drop_or_add",
    )
    annotations, authorities, bindings, indices = [], set(), set(), []
    for row, candidate in zip(rows, candidates, strict=True):
        authority, index, kind, layer = _candidate(candidate)
        encoded = _bound_representation(row, candidate)
        require(
            candidate["task_id"] == package.get("task_id", candidate["task_id"])
            and (
                "actual_method" not in candidate
                or candidate["actual_method"]
                == package.get("actual_method", candidate["actual_method"])
            ),
            "layers.original_package_task_and_method",
        )
        authorities.add(authority)
        bindings.add(encoded["tokenizer_binding_id"])
        indices.append(index)
        annotations.append(
            dict(
                candidate_id=candidate["id"],
                row_sha256=sha(encode(row)),
                representation_id=encoded["id"],
                target_raw_sha256=candidate["target_raw_sha256"],
                original_response_index=index,
                parsed_submission_kind=kind,
                layer_masks=_masks(encoded["target_mask"], layer),
            )
        )
    require(len(authorities) == len(bindings) == 1, "layers.no_mixed_source_or_tokenizer_authority")
    require(indices == sorted(set(indices)), "layers.original_temporal_order_not_layer_grouped")
    require(
        len({candidate["session_id"] for candidate in candidates}) == 1
        and [row["parsed_submission_kind"] for row in annotations].count("final") == 1
        and annotations[-1]["parsed_submission_kind"] == "final",
        "layers.one_complete_original_session_first_Final_last",
    )
    binding = next(iter(bindings))
    require(
        package.get("tokenizer_binding_id", binding) == binding,
        "layers.package_tokenizer_binding_unchanged",
    )
    return record(
        ANNOTATION_KIND,
        package_id=identifier,
        original_rows_sha256=sha(encode(rows)),
        tokenizer_binding_id=binding,
        profile="public_tf",
        source_authority=next(iter(authorities)),
        CPU_only=False,
        synthetic=False,
        rows=annotations,
        layer_token_counts=_partition(rows, annotations, "public_tf"),
        public_candidates=copy.deepcopy(candidates),
        original_whole_package_target_tokens=package["whole_package_target_tokens"],
        original_tokenization_authority="inherited_content_addressed_original_encoder",
        tokenizer_loads=0,
        retokenization=False,
        original_rows_rewritten=False,
        private_reasoning_extracted=False,
    )


def build_package_annotation(package, candidates):
    """Whole-package or exception; never returns a shortened successful package."""
    return _annotation(package, candidates)


def build_synthetic_package_annotation(package, row_layers, *, profile="public_rtf"):
    """Explicit toy masks for CPU controls, never genuine public candidate authority."""
    identifier, rows = _package(package)
    require(
        isinstance(row_layers, list) and len(row_layers) == len(rows), "layers.synthetic_all_rows"
    )
    annotated = []
    for row, value in zip(rows, row_layers, strict=True):
        require(isinstance(value, dict) or value in LAYERS, "layers.synthetic_explicit_layer")
        masks = (
            copy.deepcopy(value)
            if isinstance(value, dict)
            else _masks(row["representation"]["target_mask"], value)
        )
        annotated.append(
            {
                "candidate_id": row["candidate_id"],
                "row_sha256": sha(encode(row)),
                "layer_masks": masks,
            }
        )
    return record(
        ANNOTATION_KIND,
        package_id=identifier,
        original_rows_sha256=sha(encode(rows)),
        tokenizer_binding_id="synthetic_no_tokenizer_loaded",
        profile=profile,
        source_authority=SYNTHETIC_AUTHORITY,
        CPU_only=True,
        synthetic=True,
        rows=annotated,
        layer_token_counts=_partition(rows, annotated, profile),
        public_candidates=[],
        original_whole_package_target_tokens=package["whole_package_target_tokens"],
        synthetic_row_layers=copy.deepcopy(row_layers),
        tokenizer_loads=0,
        retokenization=False,
        original_rows_rewritten=False,
        private_reasoning_extracted=False,
    )


def validate_package_annotation(package, annotation):
    checked_record(annotation, ANNOTATION_KIND)
    if annotation.get("source_authority") == SYNTHETIC_AUTHORITY:
        expected = build_synthetic_package_annotation(
            package, annotation["synthetic_row_layers"], profile=annotation["profile"]
        )
    else:
        expected = _annotation(package, annotation["public_candidates"])
    require(annotation == expected, "layers.recomputed_original_public_mapping_and_exact_masks")
    return annotation
