"""A fixed finite within-state kernel and exact class-only weight views."""

from __future__ import annotations

from collections import Counter
from fractions import Fraction
from typing import Any

from .models import as_fraction, fraction_record, ratio, record, require


def build_kernel(
    inputs: dict[str, Any], dataset: dict[str, Any], tokens: dict[str, Any]
) -> dict[str, Any]:
    rows = dataset["rows"]
    token_by_row = {row["row_id"]: row for row in tokens["rows"]}
    require(len(token_by_row) == len(rows), "weights.token_row_totality")
    session_ids = list(dict.fromkeys(row["session_id"] for row in rows))
    trajectory_rows = {
        sid: [row for row in rows if row["session_id"] == sid] for sid in session_ids
    }
    counts = Counter(trajectory_rows[sid][0]["state_id"] for sid in session_ids)
    trajectories = []
    for sid, selected in trajectory_rows.items():
        state = selected[0]["state_id"]
        require(all(row["state_id"] == state for row in selected), "weights.trajectory_state")
        target_count = sum(token_by_row[row["id"]]["target_token_count"] for row in selected)
        require(target_count > 0, "weights.empty_trajectory")
        trajectories.append(
            {
                "session_id": sid,
                "session_label": selected[0]["session_label"],
                "state_id": state,
                "assignment_id": selected[0]["assignment_id"],
                "row_ids": [row["id"] for row in selected],
                "row_count": len(selected),
                "target_token_count": target_count,
                "within_state_probability": ratio(1, counts[state]),
            }
        )
    return record(
        "materialization_kernel",
        dataset_id=dataset["id"],
        tokenized_dataset_id=tokens["id"],
        representation_contract_id=dataset["representation_contract_id"],
        tokenizer_binding_id=tokens["tokenizer_binding_id"],
        original_partition_id=inputs["partition"]["id"],
        condition=inputs["empirical_measurement"]["condition"],
        trajectories=trajectories,
        state_support=[
            {"state_id": state, "trajectory_count": counts[state]} for state in sorted(counts)
        ],
        materialization_rule="uniform original trajectories conditional on each fixed state",
        trajectory_loss_rule="mean over all supervised raw-content tokens of that trajectory",
        independently_observed_trajectories=len(session_ids),
        new_trajectories=0,
        fresh_generation_kernel=False,
        resampling_copies_count_as_new_samples=False,
    )


def build_views(
    inputs: dict[str, Any],
    dataset: dict[str, Any],
    tokens: dict[str, Any],
    kernel: dict[str, Any],
    batch: dict[str, Any],
) -> list[dict[str, Any]]:
    states = [item["state_id"] for item in kernel["state_support"]]
    frequencies = {
        item["state_id"]: item["conditional"]
        for item in inputs["empirical_measurement"]["conditional_distribution"]
    }
    require(set(states) == set(frequencies), "weights.measured_support")
    views = []
    for name in ("P", "Q"):
        pi = {
            state: Fraction(frequencies[state]["numerator"], frequencies[state]["denominator"])
            if name == "P"
            else Fraction(1, len(states))
            for state in states
        }
        require(sum(pi.values()) == 1, "weights.class_total")
        trajectory_weights = []
        by_session = {}
        for item in kernel["trajectories"]:
            probability = pi[item["state_id"]] * as_fraction(item["within_state_probability"])
            coefficient = probability / item["target_token_count"]
            value = {
                "session_id": item["session_id"],
                "state_id": item["state_id"],
                "probability": fraction_record(probability),
                "token_coefficient": fraction_record(coefficient),
            }
            trajectory_weights.append(value)
            by_session[item["session_id"]] = value
        views.append(
            record(
                "weight_view",
                name=name,
                kernel_id=kernel["id"],
                dataset_id=dataset["id"],
                tokenized_dataset_id=tokens["id"],
                tokenizer_binding_id=tokens["tokenizer_binding_id"],
                representation_contract_id=dataset["representation_contract_id"],
                base_batch_id=batch["id"],
                row_ids=[row["id"] for row in dataset["rows"]],
                pi=[
                    {"state_id": state, "probability": fraction_record(pi[state])}
                    for state in states
                ],
                trajectory_weights=trajectory_weights,
                row_weights=[
                    {
                        "row_id": row["id"],
                        "session_id": row["session_id"],
                        "state_id": row["state_id"],
                        "token_coefficient": by_session[row["session_id"]]["token_coefficient"],
                    }
                    for row in dataset["rows"]
                ],
                interpretation="chosen empirical baseline, not optimal"
                if name == "P"
                else "balanced class-mass control, not a coverage prior or utility claim",
                applied_to_loss=True,
                normalization_after_weighted_sum=False,
                only_class_mass_intervention=True,
                training_release=False,
            )
        )
    return views


def mass_summary(kernel: dict[str, Any], views: list[dict[str, Any]]) -> dict[str, Any]:
    trajectories = kernel["trajectories"]
    total_tokens = sum(item["target_token_count"] for item in trajectories)
    total_rows = sum(item["row_count"] for item in trajectories)
    diagnostics = []
    for state in kernel["state_support"]:
        selected = [item for item in trajectories if item["state_id"] == state["state_id"]]
        diagnostics.append(
            {
                "state_id": state["state_id"],
                "equal_row_implicit_mass": ratio(
                    sum(item["row_count"] for item in selected), total_rows
                ),
                "global_target_token_mean_implicit_mass": ratio(
                    sum(item["target_token_count"] for item in selected), total_tokens
                ),
            }
        )
    return record(
        "mass_summary",
        kernel_id=kernel["id"],
        target_token_total=total_tokens,
        row_total=total_rows,
        naive_normalizations=diagnostics,
        views=[
            {
                "name": view["name"],
                "view_id": view["id"],
                "class_masses": view["pi"],
                "trajectory_weights": view["trajectory_weights"],
            }
            for view in views
        ],
        row_or_global_token_means_are_not_the_registered_objective=True,
    )
