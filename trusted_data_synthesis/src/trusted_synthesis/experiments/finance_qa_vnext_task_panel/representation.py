"""Fresh panel data binding and exact 32,768-token CPU supervision packages.

The reusable policy contains no session/candidate IDs.  Runtime-produced data has
its own identity, including every registered outcome, and completeness uses the
eligible session's admitted events rather than its token-fit subset.  This module
does not execute Finance, qualify sessions, call a Provider, or load a Student.
"""

from __future__ import annotations

from collections import Counter
from typing import Any

from trusted_synthesis.canonical_json import canonical_json_bytes

from ..finance_qa_vnext_length_adaptation import core as length_core
from ..finance_qa_vnext_model_execution import representation as original
from ..finance_qa_vnext_model_execution.models import identity, record, require, sha

MAXIMUM_SEQUENCE_LENGTH = 32_768
ARRAYS = ("input_ids", "attention_mask", "target_mask", "labels")
assets = original.frozen_tokenizer_assets


def representation_policy(binding: dict[str, Any]) -> dict[str, Any]:
    """Read the same five assets, preserving their historical 24,576 binding."""
    asset = length_core.asset_binding(binding)
    return record(
        "task_panel_representation_policy",
        tokenizer_asset_id=asset["id"],
        historical_tokenizer_binding_id=binding["id"],
        historical_tokenizer_binding_is_asset_reference_only=True,
        tokenizer_assets=asset,
        maximum_sequence_length=MAXIMUM_SEQUENCE_LENGTH,
        actual_max_position_embeddings=asset["actual_max_position_embeddings"],
        rope_scaling=None,
        chat_template_sha256=binding["chat_template_sha256"],
        software_versions=binding["software_versions"],
        chat_suffix=assets.CHAT_SUFFIX,
        suffix_token_ids=assets.SUFFIX_TOKEN_IDS,
        mask_policy=assets.MASK_POLICY,
        causal_shift=1,
        padding_side="right",
        truncation=False,
        cpu_maximum_batch_size=2,
        package_semantics="all admitted per-request responses; not concatenated conversation",
        tokenizer_asset_and_software_changes=False,
        student_weights_or_training_authorized=False,
    )


def _validate_policy(policy: dict[str, Any], binding: dict[str, Any]) -> None:
    identity(policy, "task_panel_representation_policy")
    require(policy == representation_policy(binding), "panel_representation.frozen_policy")


def _eligible(qualification: dict[str, Any]) -> bool:
    return qualification.get("status") == "success" and all(
        qualification.get(key) is True
        for key in (
            "qualified",
            "model_origin_verified",
            "evidence_complete",
            "export_eligible",
            "qa_valid",
            "trajectory_valid",
        )
    )


def _validate_entries(
    rows: list[dict[str, Any]],
    entries: list[dict[str, Any]],
    generation_condition_id: str,
) -> None:
    require(isinstance(rows, list) and isinstance(entries, list), "panel_representation.lists")
    require(
        isinstance(generation_condition_id, str) and bool(generation_condition_id),
        "panel_representation.generation_condition_id",
    )
    require(
        len({entry["registration"]["id"] for entry in entries}) == len(entries)
        and len({entry["qualification"]["id"] for entry in entries}) == len(entries)
        and len({entry["label"] for entry in entries}) == len(entries)
        and len({entry["registration"]["session_id"] for entry in entries}) == len(entries),
        "panel_representation.duplicate_entries",
    )
    expected = []
    for entry in entries:
        reg, qual, session, export = (
            entry[key] for key in ("registration", "qualification", "session", "export")
        )
        identity(reg, "session_registration")
        identity(qual, "qualification")
        identity(export, "supervision_export")
        require(
            reg.get("run_condition_id") == generation_condition_id
            and entry["label"] == reg.get("label")
            and qual.get("registration_id") == reg["id"]
            and qual.get("registered_session_id") == reg["session_id"]
            and all(
                qual.get(key) == reg.get(key)
                for key in (
                    "task_id",
                    "context_id",
                    "protocol_id",
                    "task_group",
                    "task_type",
                )
            )
            and export.get("qualification_id") == qual["id"]
            and export.get("session_id") == qual.get("session_id")
            and qual.get("session_id") == (session["id"] if session is not None else None),
            "panel_representation.entry_parent_binding",
        )
        require(
            qual.get("status") in {"success", "known_failure", "unknown", "not_started"},
            "panel_representation.qualification_status",
        )
        require(
            isinstance(export.get("rows"), list)
            and export.get("candidate_count") == len(export["rows"]),
            "panel_representation.export_count",
        )
        if not _eligible(qual):
            require(not export["rows"], "panel_representation.ineligible_positive_rows")
            continue
        require(session is not None, "panel_representation.eligible_session_missing")
        original._session_binding(session, qual)
        original._qualified_domain_audit(session, qual)
        require(
            session.get("callback_binding", {}).get("origin") != "fixture"
            and export.get("session_exclusion_reasons") == [],
            "panel_representation.eligible_export",
        )
        events = session["events"]
        admitted = [event for event in events if event["receipt"]["admitted"] is True]
        require(bool(admitted), "panel_representation.eligible_admitted_events")
        require(
            len(export["rows"]) == len(admitted)
            and len({event["submission"]["id"] for event in admitted}) == len(admitted),
            "panel_representation.admitted_export_denominator",
        )
        for row, event in zip(export["rows"], admitted, strict=True):
            original._candidate(row)
            request, submission, receipt = (
                event[key]
                for key in (
                    "request",
                    "submission",
                    "receipt",
                )
            )
            require(
                row.get("registered_session_id") == reg["session_id"]
                and row.get("registration_id") == reg["id"]
                and row["session_id"] == session["id"]
                and row["qualification_id"] == qual["id"]
                and row.get("domain_audit_id") == qual["domain_audit"]["id"]
                and row["task_id"] == reg["task_id"]
                and row["context_id"] == reg["context_id"]
                and row["protocol_id"] == reg["protocol_id"]
                and row["turn_index"] == event["sequence"]
                and row["submission_id"] == submission["id"]
                and row["receipt_id"] == receipt["id"]
                and row["public_request_id"] == request["id"]
                and row["public_runtime_state_id"] == request["state"]["id"]
                and row["submission_kind"] == event["parsed"]["kind"]
                and row["target_raw_sha256"] == submission["raw_sha256"]
                and row["target_raw_byte_count"] == submission["raw_bytes"]
                and row["messages"][-1]["content"].encode("utf-8") == canonical_json_bytes(request),
                "panel_representation.original_candidate_parents",
            )
        expected.extend(export["rows"])
    require(
        canonical_json_bytes(rows) == canonical_json_bytes(expected)
        and len({row["id"] for row in rows}) == len(rows),
        "panel_representation.exact_all_eligible_exports",
    )


def validate_record(
    row: dict[str, Any],
    token: dict[str, Any],
    data_binding: dict[str, Any],
    policy: dict[str, Any],
    binding: dict[str, Any],
    tokenizer: Any,
) -> None:
    """Check consumable arrays, byte recovery and boundaries, not producer flags."""
    original._candidate(row)
    identity(token, "task_panel_token_representation")
    identity(data_binding, "task_panel_representation_data_binding")
    identity(policy, "task_panel_representation_policy")
    require(
        token["representation_data_binding_id"] == data_binding["id"]
        and token["representation_policy_id"]
        == data_binding["representation_policy_id"]
        == policy["id"]
        and token["tokenizer_asset_id"] == policy["tokenizer_asset_id"]
        and token["tokenizer_binding_id"] == binding["id"]
        and token["row_id"] == row["id"]
        and row["id"] in data_binding["candidate_ids"]
        and all(
            token[key] == row[key]
            for key in (
                "session_id",
                "task_id",
                "qualification_id",
                "public_runtime_state_id",
            )
        ),
        "panel_representation.token_parent_binding",
    )
    require(
        policy["maximum_sequence_length"]
        == token["maximum_sequence_length"]
        == MAXIMUM_SEQUENCE_LENGTH
        and token["consumable_token_representation"] is True
        and token["tokenrepresentation_status"] == "fit"
        and token["truncated"] is False,
        "panel_representation.consumable_policy",
    )
    size, start, end = (
        token[key] for key in ("sequence_length", "target_token_start", "target_token_end")
    )
    require(
        type(size) is int
        and 0 < size <= MAXIMUM_SEQUENCE_LENGTH
        and all(isinstance(token[name], list) and len(token[name]) == size for name in ARRAYS)
        and type(start) is int
        and type(end) is int
        and 0 < start < end < size
        and token["prompt_token_count"] == start
        and token["target_token_count"] == end - start
        and token["suffix_token_count"] == size - end == len(assets.SUFFIX_TOKEN_IDS)
        and token["causal_shift"] == 1
        and token["causal_target_token_start"] == start - 1
        and token["causal_target_token_end"] == end - 1,
        "panel_representation.array_shapes_and_boundaries",
    )
    ids = token["input_ids"]
    require(all(type(value) is int and value >= 0 for value in ids), "panel_representation.ids")
    mask = [int(start <= index < end) for index in range(size)]
    require(
        token["attention_mask"] == [1] * size
        and token["target_mask"] == mask
        and token["labels"] == [value if mask[index] else -100 for index, value in enumerate(ids)]
        and mask[0] == 0
        and sum(mask[1:]) == end - start,
        "panel_representation.assistant_only_mask",
    )
    prefix = tokenizer.apply_chat_template(
        row["messages"], tokenize=False, add_generation_prompt=True
    )
    target = row["target_text"]
    full = prefix + target + assets.CHAT_SUFFIX

    def decode(values: list[int]) -> bytes:
        return tokenizer.decode(
            values,
            skip_special_tokens=False,
            clean_up_tokenization_spaces=False,
        ).encode("utf-8")

    require(
        decode(ids) == full.encode("utf-8")
        and decode(ids[:start]) == prefix.encode("utf-8")
        and decode(ids[start:end]) == target.encode("utf-8")
        and ids[end:] == assets.SUFFIX_TOKEN_IDS
        and not set(ids[start:end]) & set(tokenizer.all_special_ids),
        "panel_representation.array_content_not_original",
    )
    require(
        token["rendered_sha256"] == sha(full.encode("utf-8"))
        and token["rendered_byte_count"] == len(full.encode("utf-8"))
        and token["target_raw_sha256"] == row["target_raw_sha256"]
        and token["target_raw_byte_count"] == row["target_raw_byte_count"]
        and token["target_character_start"] == len(prefix)
        and token["target_character_end"] == len(prefix) + len(target),
        "panel_representation.rendered_bytes",
    )


def session_packages(
    rows: list[dict[str, Any]],
    entries: list[dict[str, Any]],
    tokens: dict[str, Any],
) -> dict[str, Any]:
    """Retain all registered outcomes; no task-, turn- or row-count assumptions."""
    identity(tokens, "task_panel_token_representation_dataset")
    by_row = {token["row_id"]: token for token in tokens["records"]}
    require(len(by_row) == len(tokens["records"]), "panel_representation.duplicate_token_rows")
    require(set(by_row) <= {row["id"] for row in rows}, "panel_representation.foreign_token_row")
    packages = []
    for entry in entries:
        reg, qual, session = (entry[key] for key in ("registration", "qualification", "session"))
        eligible = _eligible(qual)
        candidates = {
            row["submission_id"]: row for row in rows if row["qualification_id"] == qual["id"]
        }
        admitted = (
            [event for event in session["events"] if event["receipt"]["admitted"] is True]
            if eligible and session is not None
            else []
        )
        units = []
        for event in admitted:
            row = candidates.get(event["submission"]["id"])
            token = by_row.get(row["id"]) if row else None
            if token is not None:
                identity(token, "task_panel_token_representation")
                require(
                    token["session_id"] == session["id"]
                    and token["qualification_id"] == qual["id"]
                    and token["representation_data_binding_id"]
                    == tokens["representation_data_binding_id"],
                    "panel_representation.package_token_parent",
                )
            units.append(
                {
                    "turn_index": event["sequence"],
                    "display_turn": event["sequence"] + 1,
                    "submission_id": event["submission"]["id"],
                    "candidate_id": row["id"] if row else None,
                    "kind": event["parsed"]["kind"],
                    "token_record_id": token["id"] if token else None,
                    "tokenrepresentation_status": token["tokenrepresentation_status"]
                    if token
                    else "missing",
                    "consumable": token is not None
                    and token["consumable_token_representation"] is True,
                }
            )
        complete = eligible and bool(units) and all(unit["consumable"] for unit in units)
        packages.append(
            record(
                "task_panel_session_package",
                label=entry["label"],
                registered_session_id=reg["session_id"],
                registration_id=reg["id"],
                session_id=qual.get("session_id"),
                qualification_id=qual["id"],
                task_id=reg["task_id"],
                task_group=reg["task_group"],
                task_type=reg["task_type"],
                qualification_status=qual["status"],
                positive_eligible=eligible,
                eligibility_status="positive_eligible"
                if eligible
                else "ineligible_" + qual["status"],
                representation_status="complete"
                if complete
                else "incomplete"
                if eligible
                else "not_eligible",
                representation_data_binding_id=tokens["representation_data_binding_id"],
                representation_policy_id=tokens["representation_policy_id"],
                units=units,
                expected_units=len(admitted) if eligible else None,
                consumable_units=sum(unit["consumable"] for unit in units),
                submission_kind_counts=dict(
                    sorted(Counter(unit["kind"] for unit in units).items())
                ),
                missing_or_nonconsumable_turns=[
                    unit["display_turn"] for unit in units if not unit["consumable"]
                ],
                complete=complete,
                concatenated_conversation=False,
                qualification_recomputed=False,
            )
        )
    return record(
        "task_panel_session_packages",
        rows=packages,
        registered_session_count=len(entries),
        representation_data_binding_id=tokens["representation_data_binding_id"],
        representation_policy_id=tokens["representation_policy_id"],
        positive_eligible_session_count=sum(item["positive_eligible"] for item in packages),
        complete_session_packages=sum(item["complete"] for item in packages),
        denominator_source="all admitted events of each eligible qualified session",
    )


def _collate(
    rows: list[dict[str, Any]],
    tokens: list[dict[str, Any]],
    data_binding: dict[str, Any],
    policy: dict[str, Any],
    binding: dict[str, Any],
    tokenizer: Any,
) -> tuple[dict[str, Any], bytes]:
    import numpy as np
    import torch

    from ..qa_reasoning_share_training_preflight.loss import decode_arrays, encode_arrays

    require(0 < len(rows) == len(tokens) <= 2, "panel_representation.cpu_small_batch")
    require(len({row["session_id"] for row in rows}) == 1, "panel_representation.cpu_no_splice")
    require(not torch.cuda.is_initialized(), "panel_representation.cpu_cuda_preinitialized")
    for row, token in zip(rows, tokens, strict=True):
        validate_record(row, token, data_binding, policy, binding, tokenizer)
    shape = (len(tokens), max(token["sequence_length"] for token in tokens))
    arrays = {
        "input_ids": np.full(shape, binding["pad_token_id"], dtype=np.int64),
        "labels": np.full(shape, -100, dtype=np.int64),
        "attention_mask": np.zeros(shape, dtype=np.int64),
        "target_mask": np.zeros(shape, dtype=np.int64),
    }
    for index, token in enumerate(tokens):
        for name in ARRAYS:
            arrays[name][index, : token["sequence_length"]] = token[name]
    binary = encode_arrays(arrays)
    restored = decode_arrays(binary)
    require(
        set(restored) == set(ARRAYS)
        and all(np.array_equal(restored[name], arrays[name]) for name in ARRAYS),
        "panel_representation.cpu_npz_roundtrip",
    )
    tensors = {name: torch.from_numpy(restored[name]) for name in ARRAYS}
    require(
        all(
            tensor.device.type == "cpu" and tensor.dtype == torch.int64
            for tensor in tensors.values()
        ),
        "panel_representation.cpu_device_dtype",
    )
    mask, attention = tensors["target_mask"].bool(), tensors["attention_mask"].bool()
    shifted = mask[:, 1:]
    require(
        torch.equal(tensors["labels"][mask], tensors["input_ids"][mask])
        and bool(torch.all(tensors["labels"][~mask] == -100))
        and not bool(torch.any(mask & ~attention))
        and not bool(torch.any(mask[:, 0]))
        and int(shifted.sum()) == sum(token["target_token_count"] for token in tokens)
        and bool(torch.all(attention[:, :-1][shifted]))
        and torch.equal(tensors["labels"][:, 1:][shifted], tensors["input_ids"][:, 1:][shifted]),
        "panel_representation.cpu_actual_mask_causal_predecessors",
    )
    for index, token in enumerate(tokens):
        size = token["sequence_length"]
        require(
            bool(torch.all(tensors["attention_mask"][index, :size] == 1))
            and bool(torch.all(tensors["attention_mask"][index, size:] == 0))
            and bool(torch.all(tensors["input_ids"][index, size:] == binding["pad_token_id"])),
            "panel_representation.cpu_dynamic_right_padding",
        )
    require(not torch.cuda.is_initialized(), "panel_representation.cpu_cuda_initialized")
    return record(
        "task_panel_cpu_batch",
        representation_data_binding_id=data_binding["id"],
        representation_policy_id=policy["id"],
        session_id=rows[0]["session_id"],
        candidate_ids=[row["id"] for row in rows],
        token_record_ids=[token["id"] for token in tokens],
        shape=list(shape),
        unpadded_lengths=[token["sequence_length"] for token in tokens],
        padding_side="right",
        pad_token_id=binding["pad_token_id"],
        dtype="int64",
        device="cpu",
        real_token_count=int(attention.sum()),
        target_token_count=int(mask.sum()),
        padding_token_count=int((~attention).sum()),
        causal_target_count=int(shifted.sum()),
        original_arrays_roundtrip_exact=True,
        original_content_revalidated=True,
        dynamic_padding_checked=True,
        labels_and_causal_predecessors_checked=True,
        npz_sha256=sha(binary),
        npz_byte_count=len(binary),
        student_forward_calls=0,
        student_parameter_updates=0,
        GPU_jobs=0,
    ), binary


def analyze_representation(
    rows: list[dict[str, Any]],
    session_entries: list[dict[str, Any]],
    binding: dict[str, Any],
    policy: dict[str, Any],
    generation_condition_id: str,
) -> dict[str, Any]:
    """Represent exactly the newly exported positives, while retaining all outcomes."""
    _validate_policy(policy, binding)
    _validate_entries(rows, session_entries, generation_condition_id)
    data_binding = record(
        "task_panel_representation_data_binding",
        generation_condition_id=generation_condition_id,
        representation_policy_id=policy["id"],
        tokenizer_asset_id=policy["tokenizer_asset_id"],
        registration_ids=[entry["registration"]["id"] for entry in session_entries],
        qualification_ids=[entry["qualification"]["id"] for entry in session_entries],
        registered_session_ids=[entry["registration"]["session_id"] for entry in session_entries],
        session_ids=[entry["qualification"].get("session_id") for entry in session_entries],
        export_ids=[entry["export"]["id"] for entry in session_entries],
        candidate_ids=[row["id"] for row in rows],
        original_candidate_rows_sha256=sha(canonical_json_bytes(rows)),
        all_registered_outcomes_bound=True,
        historical_candidate_rows_imported=False,
        qualification_recomputed=False,
    )
    tokenizer = assets.load_tokenizer(binding) if rows else None
    records = []
    for row in rows:
        encoded = original.encode_original_candidate(
            row,
            binding,
            tokenizer,
            maximum_sequence_length=policy["maximum_sequence_length"],
        )
        token = record(
            "task_panel_token_representation",
            **{key: value for key, value in encoded.items() if key not in {"id", "schema_version"}},
            representation_data_binding_id=data_binding["id"],
            representation_policy_id=policy["id"],
            tokenizer_asset_id=policy["tokenizer_asset_id"],
            historical_tokenizer_binding_is_asset_reference_only=True,
        )
        if token["consumable_token_representation"]:
            validate_record(row, token, data_binding, policy, binding, tokenizer)
        else:
            require(
                token["sequence_length"] > MAXIMUM_SEQUENCE_LENGTH
                and token["tokenrepresentation_status"] == "not_fit"
                and all(token[name] is None for name in ARRAYS),
                "panel_representation.not_fit_retained_without_arrays",
            )
        records.append(token)
    if tokenizer is not None:
        require(
            tokenizer.chat_template == binding["chat_template"],
            "panel_representation.template_runtime",
        )
    _validate_policy(policy, binding)
    fit_count = sum(token["consumable_token_representation"] for token in records)
    dataset = record(
        "task_panel_token_representation_dataset",
        representation_data_binding_id=data_binding["id"],
        representation_policy_id=policy["id"],
        tokenizer_asset_id=policy["tokenizer_asset_id"],
        records=records,
        candidate_count=len(rows),
        fit_count=fit_count,
        not_fit_count=len(rows) - fit_count,
        maximum_sequence_length=MAXIMUM_SEQUENCE_LENGTH,
        status="no_positive_candidates"
        if not rows
        else "all_fit"
        if fit_count == len(rows)
        else "contains_not_fit",
        positive_representation_validated=bool(rows) and fit_count == len(rows),
        tokenizer_loaded=bool(rows),
        truncated=False,
        raw_candidates_retained=True,
        historical_rows_imported=False,
        class_weights_assigned=False,
        training_or_utility_validated=False,
    )
    packages = session_packages(rows, session_entries, dataset)
    by_row = {token["row_id"]: token for token in records}
    batches, binaries = [], {}
    for entry_index, entry in enumerate(session_entries):
        selected = [
            row
            for row in rows
            if row["qualification_id"] == entry["qualification"]["id"]
            and by_row[row["id"]]["consumable_token_representation"]
        ]
        for offset in range(0, len(selected), 2):
            batch_rows = selected[offset : offset + 2]
            batch, binary = _collate(
                batch_rows,
                [by_row[row["id"]] for row in batch_rows],
                data_binding,
                policy,
                binding,
                tokenizer,
            )
            path = f"cpu_batches/session_{entry_index:02d}_{offset // 2:02d}.npz"
            binaries[path] = binary
            batches.append({"path": path, "label": entry["label"], "batch": batch})
    loaded = [candidate for item in batches for candidate in item["batch"]["candidate_ids"]]
    require(
        len(loaded) == len(set(loaded)) == fit_count
        and set(loaded)
        == {token["row_id"] for token in records if token["consumable_token_representation"]},
        "panel_representation.cpu_exhaustive_fit_rows",
    )
    cpu = record(
        "task_panel_cpu_loading",
        representation_data_binding_id=data_binding["id"],
        representation_policy_id=policy["id"],
        batches=batches,
        batch_count=len(batches),
        candidate_count=len(rows),
        fit_count=fit_count,
        not_fit_count=len(rows) - fit_count,
        loaded_records=len(loaded),
        all_fit_records_loaded=len(loaded) == fit_count,
        positive_cpu_loading_validated=bool(loaded) and len(loaded) == fit_count,
        maximum_batch_size=2,
        maximum_observed_batch_sequence_length=max(
            (item["batch"]["shape"][1] for item in batches),
            default=None,
        ),
        all_tensors_cpu=True if batches else None,
        student_weight_loads=0,
        student_forward_calls=0,
        student_parameter_updates=0,
        GPU_jobs=0,
        training_stack_or_gpu_memory_feasibility_validated=False,
    )
    return {
        "binding": data_binding,
        "tokens": dataset,
        "packages": packages,
        "cpu_loading": cpu,
        "binary_artifacts": binaries,
    }
