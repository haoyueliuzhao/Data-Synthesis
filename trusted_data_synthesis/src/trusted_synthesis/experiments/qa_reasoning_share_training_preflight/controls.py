"""Isolated mutations of this representation/weight package, not new trajectories."""

from __future__ import annotations

import copy
import json
from fractions import Fraction
from typing import Any

from .independent import audit_training
from .loss import encode_arrays
from .models import TrainingPreflightError, as_fraction, fraction_record, record, require, sha


def _rehash(value: dict[str, Any]) -> dict[str, Any]:
    kind = value["schema_version"].removeprefix("share_training_").removesuffix(".v1")
    return record(
        kind, **{key: item for key, item in value.items() if key not in {"id", "schema_version"}}
    )


def run_controls(
    inputs: dict[str, Any],
    contract: dict[str, Any],
    dataset: dict[str, Any],
    tokens: dict[str, Any],
    kernel: dict[str, Any],
    batch: dict[str, Any],
    arrays: dict[str, Any],
    views: list[dict[str, Any]],
) -> dict[str, Any]:
    cases = []
    names = (
        "target_numeric_or_field_rewrite",
        "request_replaced_with_future_state",
        "rejected_qualified_promoted",
        "M01_intermediate_promoted",
        "equal_row_mean_instead_of_trajectory_mean",
        "global_target_token_mean",
        "within_class_kernel_changed",
        "Q_text_identity_changed",
        "Q_tokenizer_identity_changed",
        "target_mask_includes_prompt",
        "target_mask_includes_EOS",
        "padding_supervised",
        "causal_labels_shifted_twice",
    )
    for name in names:
        changed_dataset, changed_tokens = copy.deepcopy(dataset), copy.deepcopy(tokens)
        changed_kernel, changed_batch = copy.deepcopy(kernel), copy.deepcopy(batch)
        changed_views = copy.deepcopy(views)
        changed_arrays = {key: value.copy() for key, value in arrays.items()}
        delta: dict[str, Any] = {"name": name}
        if name == "target_numeric_or_field_rewrite":
            row = changed_dataset["rows"][0]
            target = json.loads(row["target_text"])
            target["host_added"] = "counterfactual"
            row["target_text"] = json.dumps(target, ensure_ascii=False)
            changed_dataset["rows"][0] = _rehash(row)
            delta.update(
                row_id=dataset["rows"][0]["id"], added_field={"host_added": "counterfactual"}
            )
        elif name == "request_replaced_with_future_state":
            row = changed_dataset["rows"][0]
            row["messages"] = copy.deepcopy(dataset["rows"][1]["messages"])
            changed_dataset["rows"][0] = _rehash(row)
            delta.update(
                row_id=dataset["rows"][0]["id"], replacement_from_row_id=dataset["rows"][1]["id"]
            )
        elif name in {"rejected_qualified_promoted", "M01_intermediate_promoted"}:
            reason = (
                "rejected_submission" if name.startswith("rejected") else "nonqualified_trajectory"
            )
            excluded = next(
                row
                for row in dataset["exclusions"]
                if row["reason"] == reason
                and (reason != "nonqualified_trajectory" or row["receipt_admitted"])
            )
            row = changed_dataset["rows"][0]
            for key in ("session_id", "session_label", "turn_index", "submission_id", "receipt_id"):
                row[key] = excluded[key]
            changed_dataset["rows"][0] = _rehash(row)
            delta.update(
                original_excluded_record_id=excluded["id"],
                promoted_submission_id=excluded["submission_id"],
            )
        elif name in {"equal_row_mean_instead_of_trajectory_mean", "global_target_token_mean"}:
            total = sum(row["target_token_count"] for row in tokens["rows"])
            for index, row in enumerate(changed_views[0]["row_weights"]):
                coefficient = (
                    Fraction(1, len(dataset["rows"]) * tokens["rows"][index]["target_token_count"])
                    if name.startswith("equal_row")
                    else Fraction(1, total)
                )
                row["token_coefficient"] = fraction_record(coefficient)
            delta["replacement_row_weights"] = changed_views[0]["row_weights"]
            delta["total_weight_still_one"] = True
        elif name == "within_class_kernel_changed":
            selected = [
                item
                for item in changed_kernel["trajectories"]
                if item["within_state_probability"]["denominator"] > 1
            ]
            selected[0]["within_state_probability"] = fraction_record(Fraction(1, 2))
            for item in selected[1:]:
                item["within_state_probability"] = fraction_record(Fraction(1, 6))
            # Coherently change Q weights too; class marginals remain 1/2, but M is not fixed.
            for trajectory in selected:
                probability = Fraction(1, 2) * as_fraction(trajectory["within_state_probability"])
                omega = fraction_record(probability / trajectory["target_token_count"])
                for row in changed_views[1]["row_weights"]:
                    if row["session_id"] == trajectory["session_id"]:
                        row["token_coefficient"] = omega
                for row in changed_views[1]["trajectory_weights"]:
                    if row["session_id"] == trajectory["session_id"]:
                        row["probability"], row["token_coefficient"] = (
                            fraction_record(probability),
                            omega,
                        )
            delta["replacement_within_class_probabilities"] = [
                item["within_state_probability"] for item in selected
            ]
            delta["class_marginals_preserved"] = True
        elif name == "Q_text_identity_changed":
            changed_views[1]["dataset_id"] = "counterfactual:different_text"
            delta["replacement_dataset_id"] = changed_views[1]["dataset_id"]
        elif name == "Q_tokenizer_identity_changed":
            changed_views[1]["tokenizer_binding_id"] = "counterfactual:different_tokenizer"
            delta["replacement_tokenizer_binding_id"] = changed_views[1]["tokenizer_binding_id"]
        else:
            row_index = 0
            token = changed_tokens["rows"][row_index]
            position = (
                token["target_token_start"] - 1
                if name == "target_mask_includes_prompt"
                else token["target_token_end"]
            )
            if name == "padding_supervised":
                position = token["sequence_length"]
                require(position < changed_arrays["labels"].shape[1], "controls.padding_available")
                changed_arrays["labels"][row_index, position] = changed_arrays["input_ids"][
                    row_index, position
                ]
                changed_arrays["target_mask"][row_index, position] = 1
            elif name == "causal_labels_shifted_twice":
                position = token["target_token_start"]
                token["labels"][position] = token["input_ids"][position + 1]
                changed_arrays["labels"][row_index, position] = token["labels"][position]
            else:
                token["labels"][position] = token["input_ids"][position]
                token["target_mask"][position] = 1
                changed_arrays["labels"][row_index, position] = token["labels"][position]
                changed_arrays["target_mask"][row_index, position] = 1
            changed_tokens["rows"][row_index] = _rehash(token)
            delta.update(row_index=row_index, token_position=position)
        changed_dataset, changed_tokens = _rehash(changed_dataset), _rehash(changed_tokens)
        # Rebind dependent identities coherently so semantic controls do not merely
        # trip on a stale content hash or the original batch's tokenization ID.
        changed_kernel["dataset_id"] = changed_dataset["id"]
        changed_kernel["tokenized_dataset_id"] = changed_tokens["id"]
        changed_kernel = _rehash(changed_kernel)
        changed_batch["tokenized_dataset_id"] = changed_tokens["id"]
        changed_binary = encode_arrays(changed_arrays)
        changed_batch["npz_sha256"] = sha(changed_binary)
        changed_batch["npz_byte_count"] = len(changed_binary)
        changed_batch["target_token_count"] = int(changed_arrays["target_mask"].sum())
        changed_batch = _rehash(changed_batch)
        for changed_view in changed_views:
            if not (name == "Q_text_identity_changed" and changed_view["name"] == "Q"):
                changed_view["dataset_id"] = changed_dataset["id"]
            changed_view["tokenized_dataset_id"] = changed_tokens["id"]
            changed_view["kernel_id"] = changed_kernel["id"]
            changed_view["base_batch_id"] = changed_batch["id"]
        changed_views = [_rehash(view) for view in changed_views]
        code: str | None
        try:
            audit_training(
                inputs,
                contract,
                changed_dataset,
                changed_tokens,
                changed_kernel,
                changed_batch,
                changed_arrays,
                changed_views,
            )
        except TrainingPreflightError as error:
            rejected, code = True, error.code
        else:
            rejected, code = False, None
        require(rejected, "controls.mutation_not_rejected." + name)
        cases.append(
            record(
                "control",
                name=name,
                input_delta=delta,
                original_dataset_id=dataset["id"],
                original_kernel_id=kernel["id"],
                expected="rejected",
                observed="rejected",
                error_code=code,
                passed=True,
                new_model_trajectory=False,
                new_provider_calls=0,
                positive_pool_additions=0,
                Student_parameter_updates=0,
            )
        )
    return record(
        "controls",
        controls=cases,
        count=len(cases),
        passed=len(cases),
        failed=0,
        source_records_mutated=False,
        controls_are_isolated_package_mutations=True,
    )
