"""Exact original-history representation for the new basis-conditioned study.

The caller binds the original HTTP request and public response and decides which
responses are positive targets. This adapter does not infer financial validity,
actual method, complete behavior class, material selection, or training authority.
The two real guidance prefixes remain part of the original input, with separate
new-condition identities. Historical token arrays are never read or rewritten.
"""

from pathlib import Path

from trusted_synthesis.experiments.qa_reasoning_share_training_preflight import (
    tokenization as assets,
)

from .plan import SYSTEMS, encode, read_json, record, require, sha

MAX_SEQUENCE_LENGTH = 32_768
GENERATION_BASES = ("endpoint", "movement")
POSITIVE_RESPONSE_KINDS = frozenset({"message", "calculate", "read_source", "notebook", "Final"})

ASSET_PARENT = (
    "trusted_data_synthesis/artifacts/qa_vnext_finqa_support_exploration/"
    "j1_j2_nd_3rep_20260908/preparation"
)
BINDING_PATH = ASSET_PARENT + "/tokenizer_binding.json"
PARENT_POLICY_PATH = ASSET_PARENT + "/representation_policy.json"
BINDING_SHA256 = "05738f570e0c0a2a8cc59dae4b3348bbe62c8fc8b88927a258efa09595531cdb"
PARENT_POLICY_SHA256 = "e52e97a5ac2b720bee9b02d596b5a667849be1f2d5e85291990197f38b786ef3"
BINDING_ID = (
    "share_training_tokenizer_binding:"
    "19bd113181c70cdc83291facccc25e7bc28ecd789588be5020ba9940d4fbaf58"
)
PARENT_POLICY_ID = (
    "finance_qa_vnext_finqa_numeric_representation_policy:"
    "173cb50bc4be1438f3b53d39ccad786b1962886028b1e839585cc597c8e56a92"
)
SOURCE_HASH_FIELDS = (
    "request_sha256",
    "response_projection_sha256",
    "raw_response_sha256",
)


def _policy(binding):
    require(MAX_SEQUENCE_LENGTH == 32_768, "basis_tokens.existing_length_policy")
    require(
        isinstance(binding, dict)
        and binding.get("id") == BINDING_ID
        and BINDING_ID.partition(":")[2]
        == sha(encode({key: value for key, value in binding.items() if key != "id"})),
        "basis_tokens.existing_binding_identity",
    )
    require(
        binding["id"] == BINDING_ID
        and binding["maximum_sequence_length"] == 24_576
        and binding["model_max_position_embeddings"] == MAX_SEQUENCE_LENGTH
        and binding["model_rope_scaling"] is None,
        "basis_tokens.existing_assets_and_position_authority",
    )
    require(
        set(SYSTEMS) == set(GENERATION_BASES)
        and all(isinstance(SYSTEMS[basis], str) and SYSTEMS[basis] for basis in GENERATION_BASES)
        and SYSTEMS["endpoint"] != SYSTEMS["movement"],
        "basis_tokens.distinct_exact_guidance_systems",
    )
    return record(
        "basis_conditioned_token_policy",
        tokenizer_binding_id=BINDING_ID,
        inherited_representation_policy_id=PARENT_POLICY_ID,
        tokenizer_binding_path=BINDING_PATH,
        tokenizer_binding_file_sha256=BINDING_SHA256,
        inherited_policy_path=PARENT_POLICY_PATH,
        inherited_policy_file_sha256=PARENT_POLICY_SHA256,
        historical_binding_length_field=24_576,
        historical_binding_unchanged=True,
        maximum_sequence_length=MAX_SEQUENCE_LENGTH,
        model_max_position_embeddings=binding["model_max_position_embeddings"],
        model_rope_scaling=None,
        tokenizer_declared_length_is_authority=False,
        chat_template_sha256=binding["chat_template_sha256"],
        chat_suffix=assets.CHAT_SUFFIX,
        suffix_token_ids=assets.SUFFIX_TOKEN_IDS,
        generation_conditions=list(GENERATION_BASES),
        guidance_system_sha256={basis: sha(SYSTEMS[basis].encode()) for basis in GENERATION_BASES},
        input="same-interaction actual HTTP request.messages including exact original g SYSTEM",
        target="same-interaction original public assistant.raw UTF-8 content",
        guidance_prefix_retained=True,
        neutral_or_historical_N_E_prefix_substitution=False,
        source_join_authority="new source binding; tokenization does not independently rejoin HTTP",
        source_projection_is_original_http_response=False,
        original_json_errors_kept_in_later_input_history=True,
        positive_response_kinds=sorted(POSITIVE_RESPONSE_KINDS),
        positive_target_authority=(
            "caller source-bound actual public message, successful tool or Final"
        ),
        independent_public_message_targets_preserved=True,
        successful_read_source_and_notebook_targets_preserved=True,
        failed_tool_targets_excluded_by_caller_but_history_preserved=True,
        scope="new support representation and consumability only; no training authorization",
        generation_basis_is_not_actual_method=True,
        financial_eligibility_inferred=False,
        actual_method_inferred=False,
        complete_classes_inferred=False,
        material_selection_performed=False,
        new_batch_only=True,
        historical_token_rows_retokenized=False,
        mask_policy=assets.MASK_POLICY,
        automatic_assistant_mask_used=False,
        target_offset_policy="complete Unicode character coverage; byte-fallback overlaps allowed",
        target_roundtrip="exact original UTF-8 bytes; no JSON reserialization",
        truncation=False,
        overlength="retain original candidate and diagnostics; no consumable token arrays",
        boundary_failure="reject, never crop prompt or target",
        padding_side="right",
        causal_shift=1,
        arrays_before_collation_are_unpadded=True,
        package_unit="complete original session; no row-uniform class weighting implied",
        class_weights_assigned=False,
        Student_weights=False,
        Student_forward=False,
        training=False,
        NLL=False,
        greedy=False,
        GPU=False,
        Provider=False,
    )


def read_bound_metadata(root):
    """Verify frozen historical binding/policy bytes without loading a tokenizer."""
    root = Path(root)
    objects = []
    for relative, byte_count, digest in (
        (BINDING_PATH, 5_462, BINDING_SHA256),
        (PARENT_POLICY_PATH, 1_057, PARENT_POLICY_SHA256),
    ):
        path = root / relative
        require(path.is_file() and not path.is_symlink(), "basis_tokens.bound_file")
        raw = path.read_bytes()
        require(len(raw) == byte_count and sha(raw) == digest, "basis_tokens.bound_file_bytes")
        objects.append(read_json(path))
        require(path.read_bytes() == raw, "basis_tokens.bound_file_changed")
    binding, parent = objects
    require(
        parent["id"] == PARENT_POLICY_ID
        and parent["tokenizer_binding_id"] == binding["id"] == BINDING_ID
        and parent["maximum_sequence_length"] == MAX_SEQUENCE_LENGTH
        and parent["truncation"] is False
        and parent["mask_policy"] == assets.MASK_POLICY,
        "basis_tokens.inherited_policy_binding",
    )
    return binding, _policy(binding)


def load_bound_assets(root):
    """Load the exact local tokenizer only when the caller authorizes representation."""
    binding, policy = read_bound_metadata(root)
    return binding, policy, assets.load_tokenizer(binding)


def _candidate(candidate):
    require(isinstance(candidate, dict), "basis_tokens.candidate_shape")
    for key in ("id", "task_key", "session_label", "source_closeout_id"):
        require(
            isinstance(candidate.get(key), str) and bool(candidate[key]), "basis_tokens.identity"
        )
    basis = candidate.get("population")
    require(
        basis in GENERATION_BASES
        and candidate["task_key"] in {"X1", "X2"}
        and candidate["session_label"]
        in {f"{basis}_{candidate['task_key']}_{rep:02d}" for rep in range(1, 9)}
        and type(candidate.get("response_index")) is int
        and 0 <= candidate["response_index"] < 32,
        "basis_tokens.population_and_response",
    )
    for key in SOURCE_HASH_FIELDS:
        value = candidate.get(key)
        require(
            isinstance(value, str)
            and len(value) == 64
            and all(character in "0123456789abcdef" for character in value),
            "basis_tokens.source_digest",
        )
    messages = candidate.get("input_messages")
    require(
        isinstance(messages, list)
        and len(messages) >= 2
        and all(
            isinstance(message, dict)
            and set(message) == {"role", "content"}
            and message["role"] in {"system", "user", "assistant"}
            and isinstance(message["content"], str)
            for message in messages
        )
        and messages[0]["role"] == "system"
        and messages[1]["role"] == "user"
        and messages[-1]["role"] == "user",
        "basis_tokens.original_open_messages",
    )
    require(messages[0]["content"] == SYSTEMS[basis], "basis_tokens.original_condition_system")
    target = candidate.get("target_response")
    require(isinstance(target, str) and bool(target), "basis_tokens.target_text")
    require(
        sha(target.encode("utf-8")) == candidate["raw_response_sha256"],
        "basis_tokens.target_bytes",
    )
    require(
        candidate.get("response_kind") in POSITIVE_RESPONSE_KINDS,
        "basis_tokens.positive_response_kind",
    )
    # Hash the whole new-schema candidate, including real g, original history,
    # target bytes, and source joins. A rehashed target alone cannot bind a swap.
    kind, separator, digest = candidate["id"].partition(":")
    require(
        bool(kind)
        and separator == ":"
        and len(digest) == 64
        and candidate["id"]
        == kind + ":" + sha(encode({key: value for key, value in candidate.items() if key != "id"}))
        and candidate
        == record(
            kind,
            **{
                key: value
                for key, value in candidate.items()
                if key not in {"id", "schema_version"}
            },
        ),
        "basis_tokens.original_candidate_content_identity",
    )


def encode_candidate(candidate, binding, policy, tokenizer):
    """Encode unchanged original messages/content with the frozen causal mask."""
    _candidate(candidate)
    require(policy == _policy(binding), "basis_tokens.frozen_policy")
    require(tokenizer.chat_template == binding["chat_template"], "basis_tokens.runtime_template")
    messages, target = candidate["input_messages"], candidate["target_response"]
    prefix = tokenizer.apply_chat_template(messages, tokenize=False, add_generation_prompt=True)
    full = tokenizer.apply_chat_template(
        [*messages, {"role": "assistant", "content": target}],
        tokenize=False,
        add_generation_prompt=False,
    )
    require(full == prefix + target + assets.CHAT_SUFFIX, "basis_tokens.rendered_content_changed")
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
    require(ids[: len(prefix_ids)] == prefix_ids, "basis_tokens.prefix_token_mismatch")
    require(
        len(offsets) == len(ids)
        and all(0 <= left <= right <= len(full) for left, right in offsets),
        "basis_tokens.offset_shape",
    )
    require(
        not any(left < start < right or left < end < right for left, right in offsets),
        "basis_tokens.boundary_crossing",
    )
    selected = [
        index for index, (left, right) in enumerate(offsets) if start <= left < right <= end
    ]
    require(bool(selected) and selected[0] > 0, "basis_tokens.no_causal_target")
    require(
        selected == list(range(len(prefix_ids), len(prefix_ids) + len(selected))),
        "basis_tokens.target_token_interval",
    )
    target_start, target_end = selected[0], selected[-1] + 1
    covered = start
    for left, right in offsets[target_start:target_end]:
        require(
            left <= covered and start <= left < right <= end,
            "basis_tokens.target_offset_coverage",
        )
        covered = max(covered, right)
    require(covered == end, "basis_tokens.target_offset_coverage")
    target_ids = ids[target_start:target_end]
    require(
        not set(target_ids) & set(tokenizer.all_special_ids), "basis_tokens.target_special_token"
    )
    decoded = tokenizer.decode(
        target_ids, skip_special_tokens=False, clean_up_tokenization_spaces=False
    )
    require(decoded.encode("utf-8") == target.encode("utf-8"), "basis_tokens.target_decode")
    require(ids[target_end:] == assets.SUFFIX_TOKEN_IDS, "basis_tokens.suffix_tokens")
    require(encoded["attention_mask"] == [1] * len(ids), "basis_tokens.unexpected_padding")
    mask = [int(target_start <= index < target_end) for index in range(len(ids))]
    labels = [token if mask[index] else -100 for index, token in enumerate(ids)]
    require(mask[0] == 0 and sum(mask[1:]) == len(target_ids), "basis_tokens.causal_shift")
    fits = len(ids) <= MAX_SEQUENCE_LENGTH
    return record(
        "basis_conditioned_token_representation",
        candidate_id=candidate["id"],
        response_kind=candidate["response_kind"],
        population=candidate["population"],
        task_key=candidate["task_key"],
        session_label=candidate["session_label"],
        response_index=candidate["response_index"],
        source_closeout_id=candidate["source_closeout_id"],
        **{key: candidate[key] for key in SOURCE_HASH_FIELDS},
        guidance_system_sha256=policy["guidance_system_sha256"][candidate["population"]],
        tokenizer_binding_id=binding["id"],
        representation_policy_id=policy["id"],
        tokenrepresentation_status="fit" if fits else "not_fit",
        reason=None if fits else "maximum_sequence_length_exceeded",
        consumable_token_representation=fits,
        maximum_sequence_length=MAX_SEQUENCE_LENGTH,
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
        target_raw_byte_count=len(target.encode("utf-8")),
        original_candidate_retained=True,
        truncated=False,
        class_weights_assigned=False,
        boundary_checks={
            "full_render_is_exact_prefix_content_suffix": True,
            "original_guidance_system_is_preserved": True,
            "original_content_utf8_bytes_preserved": True,
            "full_token_prefix_equals_prompt_tokens": True,
            "no_token_crosses_content_boundaries": True,
            "content_offsets_cover_exact_character_interval": True,
            "content_tokens_decode_to_original_utf8_bytes": True,
            "content_token_interval_is_contiguous": True,
            "original_history_and_errors_are_masked_prompt": True,
            "prompt_and_role_header_have_zero_target_mask": True,
            "eos_and_suffix_have_zero_target_mask": True,
            "padding_is_absent_before_collation": True,
            "all_target_positions_have_causal_predecessor": True,
            "no_truncation": True,
        },
    )
