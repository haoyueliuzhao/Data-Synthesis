"""One new representation policy, reusing immutable tokenizer assets and encoding.

No model qualification, financial operation, class assignment or training occurs.
The old tokenizer binding retains its identity and 24,576 historical policy.
"""

from __future__ import annotations

from collections import Counter
from pathlib import Path
from typing import Any

from trusted_synthesis.canonical_json import canonical_json_bytes, strict_canonical_hash

from ..finance_qa_vnext_model_execution import representation as original
from ..finance_qa_vnext_model_execution.models import identity as old_identity
from ..finance_qa_vnext_model_execution.models import read_json, require, sha

assets = original.frozen_tokenizer_assets
STAGE = "finance_qa_vnext_full_trajectory_representation_length_adaptation_only"
MAXIMUM_SEQUENCE_LENGTH = 32_768
ARRAYS = ("input_ids", "attention_mask", "target_mask", "labels")
POLICY_DIFFERENCES = {
    "id",
    "schema_version",
    "maximum_sequence_length",
    "tokenrepresentation_status",
    "reason",
    "consumable_token_representation",
    *ARRAYS,
}


def record(kind: str, **fields: Any) -> dict[str, Any]:
    require(not {"id", "schema_version"} & fields.keys(), "length.identity_fields")
    body = {"schema_version": f"qa_vnext_length_adaptation_{kind}.v1", **fields}
    return {**body, "id": strict_canonical_hash(body, prefix=f"qa_vnext_length_adaptation_{kind}:")}


def identity(value: dict[str, Any], kind: str) -> None:
    expected = record(kind, **{k: v for k, v in value.items() if k not in {"id", "schema_version"}})
    require(
        canonical_json_bytes(value) == canonical_json_bytes(expected), "length.identity." + kind
    )


def asset_binding(binding: dict[str, Any]) -> dict[str, Any]:
    """Separate five-file identity and actual position authority from length policy."""
    expected = assets.record(
        "tokenizer_binding",
        **{k: v for k, v in binding.items() if k not in {"id", "schema_version"}},
    )
    require(binding == expected, "length.historical_binding_identity")
    require(binding["maximum_sequence_length"] == 24_576, "length.historical_policy_immutable")
    members, contents = assets._read_members(Path(binding["directory"]))
    config = read_json(contents["config.json"])
    token_config = read_json(contents["tokenizer_config.json"])
    require(members == binding["members"], "length.asset_members")
    require(
        config.get("max_position_embeddings") == binding["model_max_position_embeddings"]
        and type(config.get("max_position_embeddings")) is int
        and config["max_position_embeddings"] >= MAXIMUM_SEQUENCE_LENGTH
        and config.get("rope_scaling") is None
        and binding["model_rope_scaling"] is None,
        "length.actual_position_authority",
    )
    require(
        token_config["chat_template"] == binding["chat_template"]
        and sha(token_config["chat_template"].encode()) == binding["chat_template_sha256"]
        and assets._software_versions() == binding["software_versions"],
        "length.template_or_software_drift",
    )
    return record(
        "tokenizer_assets",
        historical_tokenizer_binding_id=binding["id"],
        members=members,
        chat_template_sha256=binding["chat_template_sha256"],
        software_versions=binding["software_versions"],
        model_revision=binding["model_revision"],
        model_config_sha256=sha(contents["config.json"]),
        actual_max_position_embeddings=config["max_position_embeddings"],
        actual_rope_scaling=config.get("rope_scaling"),
        tokenizer_declared_model_max_length=token_config["model_max_length"],
        tokenizer_declared_length_is_position_authority=False,
        weights_are_members=False,
    )


def freeze_condition(source: dict[str, Any]) -> dict[str, Any]:
    binding = source["binding"]
    asset = asset_binding(binding)
    return record(
        "condition",
        stage=STAGE,
        historical_teacher_condition_id=source["teacher_condition"]["id"],
        historical_supervision_dataset_id=source["dataset"]["id"],
        historical_token_dataset_id=source["old_tokens"]["id"],
        historical_tokenizer_binding_id=binding["id"],
        tokenizer_asset_id=asset["id"],
        qualification_ids=[item["id"] for item in source["qualifications"]],
        session_ids=[item["id"] for item in source["sessions"]],
        candidate_ids=[row["id"] for row in source["dataset"]["rows"]],
        previous_maximum_sequence_length=24_576,
        maximum_sequence_length=MAXIMUM_SEQUENCE_LENGTH,
        model_max_position_embeddings=asset["actual_max_position_embeddings"],
        rope_scaling=None,
        tokenizer_asset_and_software_changes=False,
        original_messages_and_target_strings=True,
        chat_suffix=assets.CHAT_SUFFIX,
        suffix_token_ids=assets.SUFFIX_TOKEN_IDS,
        mask_policy=assets.MASK_POLICY,
        causal_shift=1,
        padding_side="right",
        truncation=False,
        cpu_maximum_batch_size=2,
        package_semantics="all admitted per-request responses; not concatenated conversation",
        budget={
            "existing_sessions": 2,
            "original_candidates": 34,
            "new_length_conditions": 1,
            "new_sessions": 0,
            "provider_calls": 0,
            "finance_runtime_executions": 0,
            "new_sources": 0,
            "new_tasks": 0,
            "student_weight_loads": 0,
            "student_forward_calls": 0,
            "student_updates": 0,
            "gpu_jobs": 0,
        },
        qualification_recomputed=False,
        class_weights_assigned=False,
        old_mainline_remains_paused=True,
    )


def validate_condition(condition: dict[str, Any], source: dict[str, Any]) -> None:
    identity(condition, "condition")
    require(condition == freeze_condition(source), "length.frozen_condition_mismatch")


def compare_historical(old: dict[str, Any], new: dict[str, Any]) -> dict[str, Any]:
    old_identity(old, "token_representation")
    identity(new, "token_record")
    require(old["maximum_sequence_length"] == 24_576, "length.old_token_policy")
    require(new["maximum_sequence_length"] == MAXIMUM_SEQUENCE_LENGTH, "length.new_token_policy")
    require(
        all(new.get(key) == value for key, value in old.items() if key not in POLICY_DIFFERENCES),
        "length.historical_render_or_boundary_changed",
    )
    old_fit = old["tokenrepresentation_status"] == "fit"
    if old_fit:
        require(all(new[name] == old[name] for name in ARRAYS), "length.old_fit_arrays_changed")
    else:
        require(all(old[name] is None for name in ARRAYS), "length.old_not_fit_arrays_absent")
    return {
        "candidate_id": new["row_id"],
        "old_token_record_id": old["id"],
        "new_token_record_id": new["id"],
        "old_status": old["tokenrepresentation_status"],
        "new_status": new["tokenrepresentation_status"],
        "render_and_all_nonpolicy_diagnostics_identical": True,
        "old_consumable_arrays_existed": old_fit,
        "arrays_identical": True if old_fit else None,
        "old_not_fit_reencoded_from_original_candidate": not old_fit,
        "sequence_length": new["sequence_length"],
        "new_headroom": MAXIMUM_SEQUENCE_LENGTH - new["sequence_length"],
    }


def encode(
    source: dict[str, Any], condition: dict[str, Any], tokenizer: Any
) -> tuple[dict[str, Any], dict[str, Any]]:
    validate_condition(condition, source)
    rows, binding = source["dataset"]["rows"], source["binding"]
    old_by_id = {item["row_id"]: item for item in source["old_tokens"]["records"]}
    tokens, comparisons = [], []
    for row in rows:
        original._candidate(row)
        encoded = original.encode_original_candidate(
            row, binding, tokenizer, maximum_sequence_length=condition["maximum_sequence_length"]
        )
        token = record(
            "token_record",
            **{k: v for k, v in encoded.items() if k not in {"id", "schema_version"}},
            representation_condition_id=condition["id"],
            tokenizer_asset_id=condition["tokenizer_asset_id"],
            parent_old_token_record_id=old_by_id[row["id"]]["id"],
            historical_tokenizer_binding_is_asset_reference_only=True,
        )
        comparisons.append(compare_historical(old_by_id[row["id"]], token))
        if token["consumable_token_representation"]:
            validate_record(row, token, condition, binding, tokenizer)
        tokens.append(token)
    require(tokenizer.chat_template == binding["chat_template"], "length.runtime_template")
    require(asset_binding(binding)["id"] == condition["tokenizer_asset_id"], "length.asset_drift")
    fit_count = sum(item["consumable_token_representation"] for item in tokens)
    return record(
        "token_dataset",
        representation_condition_id=condition["id"],
        tokenizer_asset_id=condition["tokenizer_asset_id"],
        source_dataset_id=source["dataset"]["id"],
        maximum_sequence_length=MAXIMUM_SEQUENCE_LENGTH,
        records=tokens,
        candidate_count=len(rows),
        fit_count=fit_count,
        not_fit_count=len(rows) - fit_count,
        status="all_fit" if fit_count == len(rows) else "contains_not_fit",
        positive_representation_validated=bool(rows) and fit_count == len(rows),
        truncated=False,
        class_weights_assigned=False,
    ), record("historical_comparison", rows=comparisons)


def validate_record(
    row: dict[str, Any],
    token: dict[str, Any],
    condition: dict[str, Any],
    binding: dict[str, Any],
    tokenizer: Any,
) -> None:
    """Validate the actual consumable arrays, not just producer diagnostic flags."""
    original._candidate(row)
    identity(condition, "condition")
    identity(token, "token_record")
    require(
        token["representation_condition_id"] == condition["id"]
        and token["tokenizer_asset_id"] == condition["tokenizer_asset_id"]
        and token["tokenizer_binding_id"] == binding["id"]
        and token["row_id"] == row["id"]
        and row["id"] in condition["candidate_ids"]
        and all(
            token[key] == row[key]
            for key in (
                "session_id",
                "task_id",
                "qualification_id",
                "public_runtime_state_id",
            )
        ),
        "length.token_parent_binding",
    )
    require(
        condition["maximum_sequence_length"] == MAXIMUM_SEQUENCE_LENGTH
        and token["maximum_sequence_length"] == MAXIMUM_SEQUENCE_LENGTH
        and token["consumable_token_representation"] is True
        and token["tokenrepresentation_status"] == "fit"
        and token["truncated"] is False,
        "length.consumable_policy",
    )
    size = token["sequence_length"]
    require(
        type(size) is int
        and 0 < size <= MAXIMUM_SEQUENCE_LENGTH
        and all(isinstance(token[name], list) and len(token[name]) == size for name in ARRAYS),
        "length.array_shapes",
    )
    start, end = token["target_token_start"], token["target_token_end"]
    require(
        type(start) is int
        and type(end) is int
        and 0 < start < end < size
        and token["prompt_token_count"] == start
        and token["target_token_count"] == end - start
        and token["suffix_token_count"] == size - end == len(assets.SUFFIX_TOKEN_IDS)
        and token["causal_shift"] == 1
        and token["causal_target_token_start"] == start - 1
        and token["causal_target_token_end"] == end - 1,
        "length.full_sequence_and_causal_boundaries",
    )
    ids = token["input_ids"]
    require(all(type(value) is int and value >= 0 for value in ids), "length.token_ids")
    mask = [int(start <= index < end) for index in range(size)]
    require(
        token["attention_mask"] == [1] * size
        and token["target_mask"] == mask
        and token["labels"] == [value if mask[i] else -100 for i, value in enumerate(ids)]
        and mask[0] == 0
        and sum(mask[1:]) == end - start,
        "length.assistant_only_mask",
    )
    prefix = tokenizer.apply_chat_template(
        row["messages"], tokenize=False, add_generation_prompt=True
    )
    target = row["target_text"]
    full = prefix + target + assets.CHAT_SUFFIX
    decode = lambda values: tokenizer.decode(  # noqa: E731
        values, skip_special_tokens=False, clean_up_tokenization_spaces=False
    ).encode("utf-8")
    require(
        decode(ids) == full.encode("utf-8")
        and decode(ids[:start]) == prefix.encode("utf-8")
        and decode(ids[start:end]) == target.encode("utf-8")
        and ids[end:] == assets.SUFFIX_TOKEN_IDS
        and not set(ids[start:end]) & set(tokenizer.all_special_ids),
        "length.array_content_not_original",
    )
    require(
        token["rendered_sha256"] == sha(full.encode("utf-8"))
        and token["rendered_byte_count"] == len(full.encode("utf-8"))
        and token["target_raw_sha256"] == row["target_raw_sha256"]
        and token["target_raw_byte_count"] == row["target_raw_byte_count"]
        and token["target_character_start"] == len(prefix)
        and token["target_character_end"] == len(prefix) + len(target),
        "length.rendered_bytes_and_character_boundaries",
    )


def session_packages(source: dict[str, Any], tokens: dict[str, Any]) -> dict[str, Any]:
    """Completeness denominator comes from immutable admitted events, never filtered rows."""
    identity(tokens, "token_dataset")
    by_row = {item["row_id"]: item for item in tokens["records"]}
    require(len(by_row) == len(tokens["records"]), "length.duplicate_token_rows")
    originals = source["dataset"]["rows"]
    require(set(by_row) <= {row["id"] for row in originals}, "length.foreign_token_row")
    packages = []
    for label, session, qualification in zip(
        ("B01", "B02"), source["sessions"], source["qualifications"], strict=True
    ):
        candidates = {
            row["submission_id"]: row for row in originals if row["session_id"] == session["id"]
        }
        admitted = [event for event in session["events"] if event["receipt"]["admitted"] is True]
        units = []
        for event in admitted:
            row = candidates.get(event["submission"]["id"])
            require(row is not None, "length.source_admitted_candidate_missing")
            token = by_row.get(row["id"])
            if token is not None:
                identity(token, "token_record")
                require(
                    token["session_id"] == session["id"]
                    and token["qualification_id"] == qualification["id"]
                    and token["representation_condition_id"]
                    == tokens["representation_condition_id"],
                    "length.package_parent_binding",
                )
            units.append(
                {
                    "turn_index": event["sequence"],
                    "display_turn": event["sequence"] + 1,
                    "submission_id": event["submission"]["id"],
                    "candidate_id": row["id"],
                    "kind": row["submission_kind"],
                    "token_record_id": token["id"] if token else None,
                    "consumable": token is not None
                    and token["consumable_token_representation"] is True,
                }
            )
        complete = bool(units) and all(unit["consumable"] for unit in units)
        packages.append(
            record(
                "session_package",
                label=label,
                session_id=session["id"],
                qualification_id=qualification["id"],
                representation_condition_id=tokens["representation_condition_id"],
                units=units,
                expected_units=len(admitted),
                consumable_units=sum(unit["consumable"] for unit in units),
                submission_kind_counts=dict(
                    sorted(Counter(unit["kind"] for unit in units).items())
                ),
                missing_or_nonconsumable_turns=[
                    unit["display_turn"] for unit in units if not unit["consumable"]
                ],
                t16_present_and_consumable=any(
                    unit["display_turn"] == 16 and unit["consumable"] for unit in units
                ),
                complete=complete,
                concatenated_conversation=False,
                qualification_recomputed=False,
            )
        )
    return record(
        "session_packages",
        representation_condition_id=tokens["representation_condition_id"],
        rows=packages,
        complete_session_packages=sum(item["complete"] for item in packages),
    )
