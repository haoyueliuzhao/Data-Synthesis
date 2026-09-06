"""Four direct measurement-control families on copies of already loaded evidence.

Counterfactual copies are diagnostic objects, never additional model trajectories
or formal valid Assignments.  This module neither loads historical data nor runs
qualification, admission, numerical Operations, tokenization or model execution.
"""

from __future__ import annotations

import copy
from collections import Counter
from collections.abc import Callable
from functools import partial as bind_call
from typing import Any

from trusted_synthesis.canonical_json import canonical_json_bytes
from trusted_synthesis.domains.finance.qa_vnext.protocol import ProtocolError

from ..finance_qa_vnext_model_execution.models import identity, record, require, sha
from .comparison import compare_projections
from .distribution import build_distribution
from .projection import action_alignment, final_alignment, no_effect_interval


def _reseal(kind: str, value: dict[str, Any], **changes: Any) -> dict[str, Any]:
    fields = {key: item for key, item in value.items() if key not in {"id", "schema_version"}}
    return record(kind, **{**fields, **changes})


def _row(name: str, family: str, expected: str, observed: dict[str, Any], passed: bool):
    return record(
        "panel_quotient_control",
        name=name,
        family=family,
        expected=expected,
        observed=observed,
        passed=passed,
        control_evidence=True,
        additional_model_trajectory=False,
        formal_valid_assignment_created=False,
    )


def _reject(name: str, family: str, call: Callable[[], Any], **binding: Any):
    try:
        result = call()
    except ProtocolError as error:
        return _row(
            name,
            family,
            "reject_or_undetermined",
            {**binding, "outcome": "rejected", "error_code": str(error)},
            True,
        )
    undetermined = isinstance(result, dict) and result.get("status") == "undetermined"
    return _row(
        name,
        family,
        "reject_or_undetermined",
        {**binding, "outcome": "undetermined" if undetermined else "unexpected_acceptance"},
        undetermined,
    )


def _interval(entry: dict[str, Any]) -> tuple[list[dict[str, Any]], int, int]:
    events = copy.deepcopy(entry["session"]["events"])
    start = next(i for i, event in enumerate(events) if not event["receipt"]["admitted"])
    stop = next(i for i in range(start + 1, len(events)) if events[i]["receipt"]["admitted"])
    return events, start, stop


def run_controls(
    inputs: dict[str, Any],
    rule: dict[str, Any],
    projections: list[dict[str, Any]],
    comparisons: list[dict[str, Any]],
) -> dict[str, Any]:
    """Run once within the main measurement stage; retain outcomes, not fake datasets."""
    condition = inputs.get("measurement_condition")
    require(isinstance(condition, dict), "panel_quotient_controls.measurement_condition")
    assert isinstance(condition, dict)
    identity(condition, "panel_quotient_condition")
    require(condition["rule_id"] == rule["id"], "panel_quotient_controls.frozen_rule")
    entries = inputs["entries"]
    by_label = {entry["label"]: entry for entry in entries}
    by_projection = {projection["label"]: projection for projection in projections}
    original_bytes = canonical_json_bytes(
        {
            "entries": entries,
            "projections": projections,
            "comparisons": comparisons,
            "condition": condition,
            "rule": rule,
        }
    )
    rows = []

    # 1. The entire already supported behavior stays unchanged, not just Final or a hash.
    compatible = []
    for entry in entries:
        if entry["audit"]["projection_supported"] is not True:
            continue
        projection = by_projection[entry["label"]]
        behavior = projection.get("behavior_projection")
        original = canonical_json_bytes(entry["old_projection"])
        new_base = (
            canonical_json_bytes({key: behavior[key] for key in ("nodes", "final")})
            if behavior
            else None
        )
        compatible.append(
            {
                "label": entry["label"],
                "qualification_id": entry["qualification"]["id"],
                "projection_id": projection["id"],
                "original_projection_sha256": sha(original),
                "new_base_sha256": sha(new_base) if new_base is not None else None,
                "exact_base_bytes_equal": new_base == original,
                "supported": projection["supported"],
                "retained_interactions_empty": behavior is not None
                and behavior["retained_interactions"] == [],
            }
        )
    rows.append(
        _row(
            "twelve_clean_projections_unchanged",
            "clean_rule_compatibility",
            "twelve_exact_compatible_bases",
            {"rows": compatible, "count": len(compatible)},
            len(compatible) == 12
            and all(
                row["exact_base_bytes_equal"]
                and row["supported"]
                and row["retained_interactions_empty"]
                for row in compatible
            ),
        )
    )
    reused = []
    for old in inputs["old_pairs"]:
        matches = [
            item for item in comparisons if item.get("derived_from_old_pair_id") == old["id"]
        ]
        matched = matches[0] if len(matches) == 1 else None
        reused.append(
            {
                "task_group": old["task_group"],
                "old_pair_id": old["id"],
                "comparison_id": matched["id"] if matched else None,
                "reused_proof_verified": matched is not None
                and matched["proof_verified"] is True
                and matched["relation"] == "equivalent"
                and matched["new_isomorphism_search"] is False,
            }
        )
    rows.append(
        _row(
            "five_existing_comparison_proofs_reused",
            "clean_rule_compatibility",
            "five_reused_proofs",
            {"rows": reused, "count": len(reused)},
            len(reused) == 5 and all(row["reused_proof_verified"] for row in reused),
        )
    )

    # 2. A rejected proposal is not no-effect if saved effects or accepted information change.
    for label in ("D01", "B01"):
        for change in (
            "execution",
            "observation",
            "claim",
            "accepted_state",
            "intervening_admission",
        ):
            events, start, stop = _interval(by_label[label])
            if change == "accepted_state":
                events[start]["post_state"]["accepted_claims"][0]["proposition"]["output"] = {
                    "isolated_control_changed_accepted_information": True
                }
            elif change == "intervening_admission":
                events[start]["receipt"]["admitted"] = True
            else:
                events[start][change] = {"isolated_control_injected_effect": True}
            rows.append(
                _reject(
                    f"{label}_no_effect_rejects_{change}",
                    "no_effect_and_support_boundary",
                    bind_call(no_effect_interval, events, start, stop),
                    source_label=label,
                    source_sequence=start,
                    successor_sequence=stop,
                    mutation=change,
                )
            )
    events, start, stop = _interval(by_label["B01"])
    events[start]["parsed"]["inputs"][0]["ref_id"] = "isolated_control_different_actual_input"
    rows.append(
        _reject(
            "B01_changed_actual_input_is_not_basis_alignment",
            "no_effect_and_support_boundary",
            lambda: action_alignment(events[start], events[stop]),
            mutation="actual_input_reference",
        )
    )
    events, start, stop = _interval(by_label["D01"])
    events[start]["parsed"]["answer_claim_id"] = "isolated_control_different_answer_claim"
    rows.append(
        _reject(
            "D01_changed_answer_claim_is_not_final_alignment",
            "no_effect_and_support_boundary",
            lambda: final_alignment(events[start], events[stop]),
            mutation="answer_claim_id",
        )
    )
    events, start, stop = _interval(by_label["D01"])
    events[stop]["parsed"]["citations"] = []
    rows.append(
        _reject(
            "D01_changed_final_support_is_not_alignment",
            "no_effect_and_support_boundary",
            lambda: final_alignment(events[start], events[stop]),
            mutation="actual_final_citation_support",
        )
    )
    share_events = copy.deepcopy(by_label["S02"]["session"]["events"])
    first_final = next(
        i for i, event in enumerate(share_events) if event["parsed"]["kind"] == "final"
    )
    valid_final = next(
        i
        for i in range(first_final + 1, len(share_events))
        if share_events[i]["receipt"]["admitted"]
    )
    share_events[first_final]["parsed"]["result"]["value"] = "93.5084581"
    rows.append(
        _reject(
            "S02_unregistered_numeric_change_is_not_representation_alignment",
            "no_effect_and_support_boundary",
            lambda: final_alignment(share_events[first_final], share_events[valid_final]),
            mutation="value_not_raw_existing_claim_or_registered_projection",
        )
    )
    share_events = by_label["S02"]["session"]["events"]
    ratio_index = next(
        i
        for i, event in enumerate(share_events)
        if event["receipt"]["admitted"] and event["parsed"].get("operation") == "share_ratio"
    )
    rows.append(
        _reject(
            "S02_cannot_skip_actual_sum_to_align_rejected_ratio",
            "no_effect_and_support_boundary",
            lambda: no_effect_interval(share_events, 0, ratio_index),
            mutation="attempt_to_cross_nearest_admitted_sum_and_update",
        )
    )

    # 3. Counterfactual behavior comparisons do not grant counterfactual qualification.
    share = by_projection["S02"]
    for name in ("remove_actual_unused_sum", "replace_disclosed_denominator_with_total_claim"):
        if not share["supported"]:
            rows.append(
                _row(
                    "S02_" + name,
                    "retained_actual_behavior",
                    "unresolved_projection_is_retained_without_graph_difference_claim",
                    {
                        "outcome": "not_applicable_projection_undetermined",
                        "source_projection_id": share["id"],
                        "source_projection_status": share["status"],
                        "test_executed": False,
                        "comparison": None,
                        "behavior_difference_verified": None,
                        "projection_promoted": False,
                        "qualified_counterfactual_or_assignment_claimed": False,
                    },
                    share["status"] == "undetermined"
                    and share["behavior_projection"] is None
                    and by_label["S02"]["qualification"]["qualified"] is True,
                )
            )
            continue
        sum_node = next(
            node["node_id"]
            for node in share["behavior_projection"]["nodes"]
            if node["operation"] == "relation_sum"
        )
        altered = copy.deepcopy(share)
        behavior = altered["behavior_projection"]
        if name == "remove_actual_unused_sum":
            behavior["nodes"] = [node for node in behavior["nodes"] if node["node_id"] != sum_node]
        else:
            ratio = next(node for node in behavior["nodes"] if node["operation"] == "share_ratio")
            denominator = next(ref for ref in ratio["inputs"] if ref["role"] == "denominator")
            denominator["kind"] = "claim"
            denominator["reference"] = {"producer_action": sum_node}
            ratio["input_dependencies"] = sorted(set(ratio["input_dependencies"]) | {sum_node})
        altered = _reseal(
            "panel_quotient_projection",
            altered,
            control_evidence=True,
            counterfactual_parent_projection_id=share["id"],
            counterfactual_is_not_a_qualified_model_trajectory=True,
        )
        compared = compare_projections(share, altered)
        final_same = canonical_json_bytes(
            share["behavior_projection"]["final"]
        ) == canonical_json_bytes(behavior["final"])
        rows.append(
            _row(
                "S02_" + name,
                "retained_actual_behavior",
                "not_equivalent_with_unchanged_final",
                {
                    "source_projection_id": share["id"],
                    "counterfactual_projection_id": altered["id"],
                    "counterfactual_behavior_sha256": sha(canonical_json_bytes(behavior)),
                    "final_bytes_unchanged": final_same,
                    "comparison": compared,
                    "test_executed": True,
                    "behavior_difference_verified": compared["relation"] == "not_equivalent",
                    "qualified_counterfactual_or_assignment_claimed": False,
                },
                compared["relation"] == "not_equivalent"
                and compared["proof_verified"] is True
                and isinstance(compared["witness"], dict)
                and final_same,
            )
        )

    # 4. Frozen qualification and registered denominators cannot follow filtered projections.
    altered_projections = copy.deepcopy(projections)
    failed_index = next(i for i, item in enumerate(altered_projections) if item["label"] == "S01")
    altered_projections[failed_index] = _reseal(
        "panel_quotient_projection",
        altered_projections[failed_index],
        status="supported",
        supported=True,
        behavior_projection=copy.deepcopy(
            share["behavior_projection"]
            if share["supported"]
            else {**by_label["S02"]["old_projection"], "retained_interactions": []}
        ),
        control_evidence=True,
    )
    rows.append(
        _reject(
            "S01_cannot_gain_a_valid_projection_or_assignment",
            "frozen_population_and_failure_mass",
            lambda: build_distribution(entries, altered_projections, comparisons, condition, rule),
            mutation="failed_session_projection_promoted",
        )
    )
    altered_entries = copy.deepcopy(entries)
    failed = next(entry for entry in altered_entries if entry["label"] == "S01")
    failed["qualification"] = _reseal(
        "qualification",
        failed["qualification"],
        qualified=True,
        end_to_end_success=True,
        status="success",
    )
    rows.append(
        _reject(
            "S01_rehashed_success_cannot_replace_frozen_qualification",
            "frozen_population_and_failure_mass",
            lambda: build_distribution(altered_entries, projections, comparisons, condition, rule),
            mutation="failed_qualification_promoted_and_reidentified",
        )
    )
    reduced_entries = [entry for entry in entries if entry["label"] != "D01"]
    reduced_projections = [item for item in projections if item["label"] != "D01"]
    reduced_comparisons = [item for item in comparisons if item["task_group"] != "D"]
    rows.append(
        _reject(
            "D01_valid_observation_cannot_be_dropped",
            "frozen_population_and_failure_mass",
            lambda: build_distribution(
                reduced_entries, reduced_projections, reduced_comparisons, condition, rule
            ),
            mutation="valid_entry_and_projection_removed",
        )
    )
    reduced_condition = _reseal(
        "panel_quotient_condition",
        condition,
        registration_ids=condition["registration_ids"][:-1],
        control_evidence=True,
    )
    rows.append(
        _reject(
            "registered_condition_denominator_cannot_shrink",
            "frozen_population_and_failure_mass",
            lambda: build_distribution(entries, projections, comparisons, reduced_condition, rule),
            mutation="registration_inventory_shrunk_then_reidentified",
        )
    )
    undecided = copy.deepcopy(projections)
    target = next(i for i, item in enumerate(undecided) if item["label"] == "D01")
    undecided[target] = _reseal(
        "panel_quotient_projection",
        undecided[target],
        status="undetermined",
        supported=False,
        behavior_projection=None,
        control_evidence=True,
        errors=[{"reason": "isolated_control_uninterpreted_valid_observation"}],
    )
    partial = build_distribution(entries, undecided, reduced_comparisons, condition, rule)
    task = next(item for item in partial["task_distributions"] if item["task_group"] == "D")
    rows.append(
        _row(
            "undetermined_D01_retains_valid_mass_and_null_conditional_pi",
            "frozen_population_and_failure_mass",
            "registered_16_valid_15_D_valid_2_unmapped_1_pi_null",
            {
                "registered_session_count": partial["registered_session_count"],
                "qualified_count": partial["qualified_count"],
                "historical_panel_success_fraction": partial["historical_panel_success_fraction"],
                "D_registered_session_count": task["registered_session_count"],
                "D_qualified_count": task["qualified_count"],
                "D_unmapped_qualified_count": task["unmapped_qualified_count"],
                "D_mapped_joint_mass": task["mapped_joint_mass"],
                "D_unmapped_joint_mass": task["unmapped_joint_mass"],
                "D_conditional_distribution": task["conditional_distribution"],
                "counterfactual_distribution_assignments_written": 0,
            },
            partial["registered_session_count"] == 16
            and partial["qualified_count"] == 15
            and partial["historical_panel_success_fraction"] == {"numerator": 15, "denominator": 16}
            and task["registered_session_count"] == task["qualified_count"] == 2
            and task["unmapped_qualified_count"] == 1
            and task["conditional_distribution"] is None
            and task["mapped_joint_mass"]
            == task["unmapped_joint_mass"]
            == {"numerator": 1, "denominator": 2},
        )
    )
    unchanged = original_bytes == canonical_json_bytes(
        {
            "entries": entries,
            "projections": projections,
            "comparisons": comparisons,
            "condition": condition,
            "rule": rule,
        }
    )
    return record(
        "panel_quotient_controls",
        measurement_condition_id=condition["id"],
        rule_id=rule["id"],
        rows=rows,
        control_count=len(rows),
        executed_control_count=sum(row["observed"].get("test_executed", True) for row in rows),
        not_applicable_control_count=sum(
            row["observed"].get("test_executed") is False for row in rows
        ),
        family_counts=dict(Counter(row["family"] for row in rows)),
        family_count=4,
        all_expected_outcomes=unchanged and all(row["passed"] for row in rows),
        original_inputs_and_sidecars_unmodified=unchanged,
        original_input_and_sidecar_sha256=sha(original_bytes),
        control_evidence=True,
        standalone_repeated_audit_stage=False,
        controls_run_inside_main_measurement_stage=True,
        counterfactual_valid_assignments_written=0,
        additional_model_samples=0,
        provider_calls=0,
        historical_input_loads=0,
        runtime_executions=0,
        operation_executions=0,
        qualification_calls=0,
        tokenizer_loads=0,
        tokenizations=0,
        student_forward_calls=0,
        student_updates=0,
        gpu_jobs=0,
    )
