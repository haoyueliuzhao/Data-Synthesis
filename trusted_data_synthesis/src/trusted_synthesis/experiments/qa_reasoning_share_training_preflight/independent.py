"""Independent text/mask/kernel/class-mass validation over one fixed training package.

Tokenizer rendering/decoding remains the bound tokenizer producer's evidence.
This checker neither retokenizes nor calls the kernel, view, collator or loss
producer. NPZ container bytes and actual controlled-NLL executions are checked
separately by the persisted-package workflow.
"""

from __future__ import annotations

from collections import Counter, defaultdict
from fractions import Fraction
from typing import Any

import numpy as np

from .inputs import validate_text_dataset
from .models import (
    TrainingPreflightError,
    as_fraction,
    fraction_record,
    identity,
    record,
    require,
    sha,
)

ARRAY_DTYPES = {
    "input_ids": "int64",
    "labels": "int64",
    "attention_mask": "int8",
    "target_mask": "int8",
}
BOUNDARY_CHECKS = {
    "full_render_is_exact_prefix_content_suffix",
    "original_content_utf8_bytes_preserved",
    "full_token_prefix_equals_prompt_tokens",
    "no_token_crosses_content_boundaries",
    "content_offsets_partition_exact_character_interval",
    "content_tokens_decode_to_original_utf8_bytes",
    "content_token_interval_is_contiguous",
    "prompt_and_role_header_have_zero_target_mask",
    "eos_and_suffix_have_zero_target_mask",
    "padding_is_absent_before_collation",
    "all_target_positions_have_causal_predecessor",
    "no_truncation",
}


def _token_rows(
    contract: dict[str, Any],
    dataset: dict[str, Any],
    tokens: dict[str, Any],
) -> tuple[dict[str, dict[str, Any]], dict[str, int]]:
    identity(tokens)
    require(
        tokens["schema_version"] == "share_training_tokenized_dataset.v1"
        and tokens["dataset_id"] == dataset["id"]
        and tokens["representation_contract_id"] == contract["id"]
        and tokens["tokenizer_binding_id"] == contract["tokenizer_binding_id"]
        and tokens["truncated"] is False
        and tokens["target_mask_policy"] == "exact original assistant content only",
        "independent.tokenized_dataset_binding",
    )
    require(
        [row["row_id"] for row in tokens["rows"]] == [row["id"] for row in dataset["rows"]],
        "independent.token_row_order",
    )
    selected = {}
    totals: dict[str, int] = defaultdict(int)
    for text, token in zip(dataset["rows"], tokens["rows"], strict=True):
        identity(token)
        require(
            token["schema_version"] == "share_training_tokenized_row.v1"
            and token["row_id"] == text["id"]
            and token["session_id"] == text["session_id"]
            and token["state_id"] == text["state_id"]
            and token["tokenizer_binding_id"] == tokens["tokenizer_binding_id"]
            and token["target_raw_sha256"]
            == sha(text["target_text"].encode("utf-8"))
            == text["target_sha256"],
            "independent.token_original_row_binding",
        )
        length, start, end = (
            token["sequence_length"],
            token["target_token_start"],
            token["target_token_end"],
        )
        require(
            all(type(value) is int for value in (length, start, end))
            and 0 < start < end <= length <= contract["maximum_sequence_length"]
            and token["truncated"] is False
            and token["prompt_token_count"] == start
            and token["target_token_count"] == end - start
            and token["suffix_token_count"] == length - end > 0
            and type(token["target_character_start"]) is int
            and type(token["target_character_end"]) is int
            and token["target_character_start"] > 0
            and token["target_character_end"] - token["target_character_start"]
            == len(text["target_text"])
            and type(token["rendered_byte_count"]) is int
            and token["rendered_byte_count"] > text["target_byte_count"]
            and isinstance(token["rendered_sha256"], str)
            and len(token["rendered_sha256"]) == 64,
            "independent.target_span_and_no_truncation",
        )
        require(
            set(token["boundary_checks"]) == BOUNDARY_CHECKS
            and all(value is True for value in token["boundary_checks"].values()),
            "independent.primary_tokenizer_boundary_evidence",
        )
        for name in ARRAY_DTYPES:
            require(
                isinstance(token[name], list)
                and len(token[name]) == length
                and all(type(value) is int for value in token[name]),
                "independent.token_array_shape",
            )
        require(all(value >= 0 for value in token["input_ids"]), "independent.token_id_domain")
        mask = [int(start <= position < end) for position in range(length)]
        labels = [
            value if mask[position] else contract["label_ignore_index"]
            for position, value in enumerate(token["input_ids"])
        ]
        require(
            token["attention_mask"] == [1] * length
            and token["target_mask"] == mask
            and sum(token["target_mask"]) == token["target_token_count"],
            "independent.exact_content_only_mask",
        )
        require(token["labels"] == labels, "independent.unshifted_causal_labels")
        require(
            contract["causal_label_shift"] == 1
            and token["target_mask"][0] == 0
            and sum(token["target_mask"][1:]) == token["target_token_count"],
            "independent.causal_target_predecessors",
        )
        selected[text["id"]] = token
        totals[text["session_id"]] += end - start
    return selected, dict(totals)


def _fixed_kernel(
    inputs: dict[str, Any],
    dataset: dict[str, Any],
    tokens: dict[str, Any],
    kernel: dict[str, Any],
    totals: dict[str, int],
) -> dict[str, dict[str, Any]]:
    identity(kernel)
    require(
        kernel["schema_version"] == "share_training_materialization_kernel.v1"
        and kernel["dataset_id"] == dataset["id"]
        and kernel["tokenized_dataset_id"] == tokens["id"]
        and kernel["representation_contract_id"] == dataset["representation_contract_id"]
        and kernel["tokenizer_binding_id"] == tokens["tokenizer_binding_id"]
        and kernel["original_partition_id"] == inputs["partition"]["id"]
        and kernel["condition"] == inputs["empirical_measurement"]["condition"],
        "independent.kernel_binding",
    )
    assignments = {item["session_id"]: item for item in inputs["assignments"]}
    order = list(dict.fromkeys(row["session_id"] for row in dataset["rows"]))
    by_state = Counter(item["state_id"] for item in assignments.values())
    require(
        set(order) == set(assignments) == set(totals), "independent.kernel_original_trajectories"
    )
    require(
        [item["session_id"] for item in kernel["trajectories"]] == order,
        "independent.kernel_trajectory_order",
    )
    expected = {}
    for item in kernel["trajectories"]:
        sid = item["session_id"]
        assignment = assignments[sid]
        rows = [row for row in dataset["rows"] if row["session_id"] == sid]
        state = assignment["state_id"]
        require(
            item["session_label"] == rows[0]["session_label"]
            and item["state_id"] == state
            and item["assignment_id"] == assignment["id"]
            and item["row_ids"] == [row["id"] for row in rows]
            and item["row_count"] == len(rows)
            and type(item["target_token_count"]) is int
            and item["target_token_count"] == totals[sid] > 0,
            "independent.kernel_complete_trajectory_tokens",
        )
        within = Fraction(1, by_state[state])
        require(
            as_fraction(item["within_state_probability"]) == within,
            "independent.fixed_uniform_within_state_kernel",
        )
        expected[sid] = {"state_id": state, "within": within, "target_tokens": totals[sid]}
    require(
        kernel["state_support"]
        == [{"state_id": state, "trajectory_count": by_state[state]} for state in sorted(by_state)]
        and kernel["independently_observed_trajectories"] == len(assignments) == 5
        and kernel["new_trajectories"] == 0
        and kernel["fresh_generation_kernel"] is False
        and kernel["resampling_copies_count_as_new_samples"] is False
        and kernel["materialization_rule"]
        == "uniform original trajectories conditional on each fixed state"
        and kernel["trajectory_loss_rule"]
        == "mean over all supervised raw-content tokens of that trajectory",
        "independent.fixed_materialization_domain",
    )
    return expected


def _base_arrays(
    contract: dict[str, Any],
    dataset: dict[str, Any],
    tokens: dict[str, Any],
    batch: dict[str, Any],
    arrays: dict[str, Any],
) -> None:
    identity(batch)
    rows = tokens["rows"]
    width = max(row["sequence_length"] for row in rows)
    shape = (len(rows), width)
    require(
        batch["schema_version"] == "share_training_base_batch.v1"
        and batch["tokenized_dataset_id"] == tokens["id"]
        and batch["row_ids"] == [row["id"] for row in dataset["rows"]]
        and batch["shape"] == list(shape)
        and batch["padding_side"] == contract["padding_side"] == "right"
        and type(batch["pad_token_id"]) is int
        and batch["pad_token_id"] >= 0
        and batch["array_dtypes"] == ARRAY_DTYPES
        and batch["truncated"] is False
        and batch["target_excludes_prompt_suffix_padding"] is True
        and batch["shared_by_views"] == ["P", "Q"],
        "independent.base_batch_binding",
    )
    require(set(arrays) == set(ARRAY_DTYPES), "independent.base_array_domain")
    for name, dtype in ARRAY_DTYPES.items():
        require(
            isinstance(arrays[name], np.ndarray)
            and arrays[name].shape == shape
            and str(arrays[name].dtype) == dtype,
            "independent.base_array_shape_dtype",
        )
    for index, row in enumerate(rows):
        length = row["sequence_length"]
        for name in ARRAY_DTYPES:
            require(
                np.array_equal(arrays[name][index, :length], np.asarray(row[name])),
                "independent.base_array_original_tokens",
            )
            padding = (
                batch["pad_token_id"]
                if name == "input_ids"
                else contract["label_ignore_index"]
                if name == "labels"
                else 0
            )
            require(
                bool(np.all(arrays[name][index, length:] == padding)),
                "independent.zero_loss_right_padding",
            )
    real = sum(row["sequence_length"] for row in rows)
    target = sum(row["target_token_count"] for row in rows)
    require(
        batch["real_token_count"] == real == int(arrays["attention_mask"].sum())
        and batch["target_token_count"] == target == int(arrays["target_mask"].sum())
        and batch["padding_token_count"] == len(rows) * width - real
        and int(arrays["target_mask"][:, 1:].sum()) == target
        and np.array_equal(
            arrays["labels"][:, 1:] != contract["label_ignore_index"],
            arrays["target_mask"][:, 1:] == 1,
        ),
        "independent.batch_counts_and_causal_alignment",
    )


def _class_views(
    inputs: dict[str, Any],
    dataset: dict[str, Any],
    tokens: dict[str, Any],
    kernel: dict[str, Any],
    batch: dict[str, Any],
    views: list[dict[str, Any]],
    token_rows: dict[str, dict[str, Any]],
    trajectories: dict[str, dict[str, Any]],
) -> list[dict[str, Any]]:
    require([view["name"] for view in views] == ["P", "Q"], "independent.exact_two_weight_views")
    states = sorted({item["state_id"] for item in trajectories.values()})
    frozen_frequencies = inputs["empirical_measurement"]["conditional_distribution"]
    baseline = {
        item["state_id"]: Fraction(
            item["conditional"]["numerator"], item["conditional"]["denominator"]
        )
        for item in frozen_frequencies
    }
    require(set(baseline) == set(states) and len(states) == 2, "independent.closed_class_support")
    summaries = []
    for view in views:
        identity(view)
        require(
            view["schema_version"] == "share_training_weight_view.v1"
            and view["kernel_id"] == kernel["id"]
            and view["dataset_id"] == dataset["id"]
            and view["tokenized_dataset_id"] == tokens["id"]
            and view["tokenizer_binding_id"] == tokens["tokenizer_binding_id"]
            and view["representation_contract_id"] == dataset["representation_contract_id"]
            and view["base_batch_id"] == batch["id"]
            and view["row_ids"] == [row["id"] for row in dataset["rows"]]
            and view["applied_to_loss"] is True
            and view["normalization_after_weighted_sum"] is False
            and view["only_class_mass_intervention"] is True
            and view["training_release"] is False,
            "independent.shared_representation_only_class_intervention",
        )
        pi = (
            baseline
            if view["name"] == "P"
            else {state: Fraction(1, len(states)) for state in states}
        )
        require(
            [item["state_id"] for item in view["pi"]] == states
            and all(as_fraction(item["probability"]) == pi[item["state_id"]] for item in view["pi"])
            and sum(pi.values()) == 1,
            "independent.registered_class_probability",
        )
        require(
            [item["session_id"] for item in view["trajectory_weights"]] == list(trajectories),
            "independent.complete_trajectory_weights",
        )
        coefficients = {}
        probabilities = {}
        for item in view["trajectory_weights"]:
            sid = item["session_id"]
            actual = trajectories[sid]
            probability = pi[actual["state_id"]] * actual["within"]
            coefficient = probability / actual["target_tokens"]
            require(
                item["state_id"] == actual["state_id"]
                and as_fraction(item["probability"]) == probability
                and as_fraction(item["token_coefficient"]) == coefficient,
                "independent.pi_times_M_over_trajectory_tokens",
            )
            coefficients[sid], probabilities[sid] = coefficient, probability
        require(
            [item["row_id"] for item in view["row_weights"]]
            == [row["id"] for row in dataset["rows"]],
            "independent.complete_row_weights",
        )
        trajectory_mass: dict[str, Fraction] = defaultdict(Fraction)
        class_mass: dict[str, Fraction] = defaultdict(Fraction)
        for row, weight in zip(dataset["rows"], view["row_weights"], strict=True):
            sid = row["session_id"]
            coefficient = as_fraction(weight["token_coefficient"])
            require(
                weight["session_id"] == sid
                and weight["state_id"] == row["state_id"]
                and coefficient == coefficients[sid],
                "independent.fixed_per_target_token_coefficient",
            )
            mass = coefficient * sum(token_rows[row["id"]]["target_mask"])
            trajectory_mass[sid] += mass
            class_mass[row["state_id"]] += mass
        require(
            dict(trajectory_mass) == probabilities
            and dict(class_mass) == pi
            and sum(trajectory_mass.values()) == sum(class_mass.values()) == 1,
            "independent.actual_token_class_and_trajectory_mass",
        )
        for sid, item in trajectories.items():
            require(
                trajectory_mass[sid] / class_mass[item["state_id"]] == item["within"],
                "independent.within_class_ratio_preserved",
            )
        summaries.append(
            {
                "name": view["name"],
                "view_id": view["id"],
                "total_mass": fraction_record(sum(class_mass.values(), Fraction(0))),
                "class_masses": [
                    {"state_id": state, "mass": fraction_record(class_mass[state])}
                    for state in states
                ],
                "trajectory_masses": [
                    {"session_id": sid, "mass": fraction_record(trajectory_mass[sid])}
                    for sid in trajectories
                ],
            }
        )
    return summaries


def audit_training(
    inputs: dict[str, Any],
    contract: dict[str, Any],
    dataset: dict[str, Any],
    tokens: dict[str, Any],
    kernel: dict[str, Any],
    batch: dict[str, Any],
    arrays: dict[str, Any],
    views: list[dict[str, Any]],
) -> dict[str, Any]:
    """Raise on mismatch; otherwise certify masks and exact intended class masses."""
    try:
        text_validation = validate_text_dataset(inputs, contract, dataset)
        checks = ["exact_original_text_and_membership"]
        token_rows, totals = _token_rows(contract, dataset, tokens)
        checks.append("token_spans_masks_labels_and_causal_alignment")
        trajectories = _fixed_kernel(inputs, dataset, tokens, kernel, totals)
        checks.append("fixed_original_uniform_within_state_kernel")
        _base_arrays(contract, dataset, tokens, batch, arrays)
        checks.append("CPU_tensor_contents_right_padding_and_counts")
        masses = _class_views(
            inputs, dataset, tokens, kernel, batch, views, token_rows, trajectories
        )
        checks.append("class_only_intervention_and_exact_pi_M_token_mass")
        return record(
            "independent_validation",
            passed=True,
            checks=checks,
            dataset_id=dataset["id"],
            tokenized_dataset_id=tokens["id"],
            kernel_id=kernel["id"],
            base_batch_id=batch["id"],
            view_ids=[view["id"] for view in views],
            text_validation_id=text_validation["id"],
            actual_target_token_count=sum(totals.values()),
            trajectory_target_token_counts=[
                {"session_id": sid, "target_token_count": totals[sid]} for sid in trajectories
            ],
            independently_recomputed_masses=masses,
            original_assignments_reused_not_recomputed=True,
            independent_retokenization_or_decode=False,
            tokenizer_boundary_authority="bound primary tokenizer records and exact original text",
            NPZ_container_bytes_reencoded=False,
            loss_implementation_executed_by_this_audit=False,
            controlled_NLL_results_are_not_an_input_to_this_audit=True,
            calls_tokenizer_kernel_view_collator_or_loss_producer=False,
            provider_calls=0,
            credential_reads=0,
            old_qualification_or_quotient_calls=0,
            new_candidate_runtime_executions=0,
            Student_model_loads=0,
            Student_forward_passes=0,
            Student_parameter_updates=0,
            GPU_jobs=0,
        )
    except TrainingPreflightError:
        raise
    except (ValueError, KeyError, TypeError, IndexError, ArithmeticError, RecursionError) as error:
        raise TrainingPreflightError("independent.invalid_training_package") from error
