"""Formal finite assignments and fixed-denominator empirical panel distributions.

This module consumes frozen outcomes and new projection/comparison sidecars. It
does not qualify a session, execute an Operation, interpret correction events,
search for a graph mapping, or create training rows. A checked correspondence,
not equality of artifact hashes, authorizes grouping two observations together.
"""

from __future__ import annotations

from collections import Counter
from typing import Any

from trusted_synthesis.canonical_json import canonical_json_bytes, strict_canonical_hash
from trusted_synthesis.domains.finance.qa_vnext import measurement as domain

from ..finance_qa_vnext_model_execution.models import identity, record, require
from .comparison import PARENT_FIELDS, _sidecar

GROUPS = ("F", "C", "G", "A", "D", "R", "B", "S")
TASK_FIELDS = ("task_group", "task_type", "task_id", "context_id", "protocol_id", "registry_hash")


def _fraction(numerator: int, denominator: int) -> dict[str, int]:
    require(
        type(numerator) is int and type(denominator) is int and denominator > 0,
        "panel_quotient_distribution.fraction",
    )
    return {"numerator": numerator, "denominator": denominator}


def _identified(value: dict[str, Any]) -> None:
    """Check a frozen record reference without invoking its producer or validator."""
    ref = value.get("id")
    require(isinstance(ref, str) and ":" in ref, "panel_quotient_distribution.record_identity")
    assert isinstance(ref, str)
    require(
        ref
        == strict_canonical_hash(
            {key: item for key, item in value.items() if key != "id"},
            prefix=ref.split(":", 1)[0] + ":",
        ),
        "panel_quotient_distribution.record_identity",
    )


def _inventory(
    entries: list[dict[str, Any]],
    projections: list[dict[str, Any]],
    condition: dict[str, Any],
    rule: dict[str, Any],
) -> tuple[list[dict[str, Any]], dict[str, dict[str, Any]]]:
    identity(condition, "panel_quotient_condition")
    _identified(rule)
    require(condition["rule_id"] == rule["id"], "panel_quotient_distribution.frozen_rule")
    require(
        len(entries) == len(projections) == 16, "panel_quotient_distribution.registered_denominator"
    )
    require(
        condition.get("original_registration_count", 16) == 16
        and condition.get("original_qualified_count", 15) == 15
        and condition.get("task_marginal", {group: _fraction(1, 8) for group in GROUPS})
        == {group: _fraction(1, 8) for group in GROUPS},
        "panel_quotient_distribution.frozen_denominator_or_marginal",
    )
    for field in ("registration_ids", "qualification_ids", "session_ids"):
        require(
            len(condition[field]) == len(set(condition[field])) == 16,
            "panel_quotient_distribution.frozen_population",
        )
    expected_qualified = set(condition["qualified_qualification_ids"])
    require(
        len(expected_qualified) == len(condition["qualified_qualification_ids"]) == 15
        and expected_qualified < set(condition["qualification_ids"]),
        "panel_quotient_distribution.frozen_valid_population",
    )
    require(
        len({entry["label"] for entry in entries}) == 16
        and Counter(entry["registration"]["task_group"] for entry in entries)
        == Counter({group: 2 for group in GROUPS}),
        "panel_quotient_distribution.fixed_task_replicates",
    )
    require(
        {entry["registration"]["id"] for entry in entries} == set(condition["registration_ids"])
        and {entry["qualification"]["id"] for entry in entries}
        == set(condition["qualification_ids"])
        and {entry["session"]["id"] for entry in entries} == set(condition["session_ids"]),
        "panel_quotient_distribution.missing_or_foreign_frozen_entry",
    )
    require(
        len({entry["registration"]["task_id"] for entry in entries}) == 8,
        "panel_quotient_distribution.eight_distinct_tasks",
    )
    if "frozen_outcomes" in condition:
        outcomes = {item["label"]: item for item in condition["frozen_outcomes"]}
        expected_outcomes = {
            entry["label"]: {
                "label": entry["label"],
                "registration_id": entry["registration"]["id"],
                "qualification_id": entry["qualification"]["id"],
                "session_id": entry["session"]["id"],
                **{
                    key: entry["qualification"][key]
                    for key in ("qualified", "end_to_end_success", "status")
                },
            }
            for entry in entries
        }
        require(
            len(condition["frozen_outcomes"]) == len(outcomes) == 16
            and outcomes == expected_outcomes,
            "panel_quotient_distribution.frozen_outcome_inventory",
        )
    by_qualification = {projection["qualification_id"]: projection for projection in projections}
    require(
        len(by_qualification) == 16
        and set(by_qualification) == set(condition["qualification_ids"])
        and len({projection["id"] for projection in projections}) == 16,
        "panel_quotient_distribution.projection_inventory",
    )
    for entry in entries:
        registration, qualification, session, audit, graph, package = (
            entry[key]
            for key in ("registration", "qualification", "session", "audit", "graph", "package")
        )
        identity(registration, "session_registration")
        identity(qualification, "qualification")
        projection = by_qualification[qualification["id"]]
        _sidecar(projection)
        require(
            entry["label"] == registration["label"] == projection["label"]
            and registration["run_condition_id"] == condition["generation_condition_id"]
            and qualification["registration_id"]
            == registration["id"]
            == projection["registration_id"]
            and qualification["registered_session_id"] == registration["session_id"]
            and qualification["session_id"] == session["id"] == projection["session_id"]
            and qualification["domain_audit_id"] == audit["id"] == projection["old_domain_audit_id"]
            and qualification["domain_audit"] == audit
            and audit["actual_decision_graph"] == graph
            and audit["finite_projection"] == entry["old_projection"]
            and projection["source_actual_graph_id"] == graph["id"]
            and projection["rule_id"] == rule["id"]
            and projection["generation_condition_id"] == condition["generation_condition_id"]
            and all(qualification[key] == registration[key] for key in TASK_FIELDS)
            and all(
                projection[key] == registration[key] for key in TASK_FIELDS if key != "task_type"
            ),
            "panel_quotient_distribution.source_parent_bindings",
        )
        require(
            qualification["evidence_complete"] is True
            and qualification["model_origin_verified"] is True,
            "panel_quotient_distribution.frozen_evidence_complete",
        )
        expected_success = qualification["id"] in expected_qualified
        require(
            qualification["qualified"] is expected_success
            and qualification["end_to_end_success"] is expected_success
            and qualification["status"] == ("success" if expected_success else "known_failure"),
            "panel_quotient_distribution.frozen_outcome_not_promoted",
        )
        require(
            package["qualification_id"] == qualification["id"]
            and package["session_id"] == session["id"]
            and package["registration_id"] == registration["id"],
            "panel_quotient_distribution.representation_reference_only",
        )
        require(
            projection["old_projection_supported"] is audit["projection_supported"],
            "panel_quotient_distribution.old_support_not_rewritten",
        )
        if expected_success:
            require(
                projection["status"] in {"supported", "undetermined"},
                "panel_quotient_distribution.valid_entry_not_dropped",
            )
        else:
            require(
                projection["status"] == "ineligible"
                and not projection["supported"]
                and projection.get("behavior_projection") is None,
                "panel_quotient_distribution.failed_session_has_no_valid_projection",
            )
    ordered = sorted(
        entries,
        key=lambda entry: (GROUPS.index(entry["registration"]["task_group"]), entry["label"]),
    )
    for group in GROUPS:
        local = [entry for entry in ordered if entry["registration"]["task_group"] == group]
        require(
            all(
                local[0]["registration"][key] == local[1]["registration"][key]
                for key in TASK_FIELDS
            ),
            "panel_quotient_distribution.same_task_context",
        )
    return ordered, by_qualification


def _comparisons(
    comparisons: list[dict[str, Any]],
    projections: list[dict[str, Any]],
) -> dict[str, dict[str, Any]]:
    by_id = {projection["id"]: projection for projection in projections}
    require(len(comparisons) <= 7, "panel_quotient_distribution.same_task_pair_budget")
    by_group = {}
    for comparison in comparisons:
        identity(comparison, "panel_quotient_comparison")
        left = by_id.get(comparison["left_projection_id"])
        right = by_id.get(comparison["right_projection_id"])
        require(
            left is not None and right is not None and left["id"] != right["id"],
            "panel_quotient_distribution.pair_population",
        )
        assert left is not None and right is not None
        require(
            left["status"] != "ineligible"
            and right["status"] != "ineligible"
            and all(left[key] == right[key] == comparison[key] for key in PARENT_FIELDS),
            "panel_quotient_distribution.pair_source_domain",
        )
        require(
            comparison["task_group"] not in by_group,
            "panel_quotient_distribution.duplicate_task_pair",
        )
        relation = comparison["relation"]
        require(
            relation in {"equivalent", "not_equivalent", "undetermined"},
            "panel_quotient_distribution.comparison_relation",
        )
        expected_equivalent = {"equivalent": True, "not_equivalent": False, "undetermined": None}[
            relation
        ]
        require(
            comparison["equivalent"] is expected_equivalent
            and comparison["content_hash_is_relation_authority"] is False
            and comparison["proof_verified"] is (relation != "undetermined")
            and comparison["exact_full_graph_and_retained_interactions_compared"]
            is (relation != "undetermined"),
            "panel_quotient_distribution.comparison_proof_status",
        )
        if relation == "undetermined":
            require(
                comparison["correspondence"] is None
                and comparison["witness"] is None
                and isinstance(comparison["reason"], str),
                "panel_quotient_distribution.undetermined_has_no_relation_proof",
            )
        else:
            require(
                left["supported"] and right["supported"] and comparison["reason"] is None,
                "panel_quotient_distribution.determinate_pair_support",
            )
            if relation == "equivalent":
                mapping = comparison["correspondence"]
                left_graph, right_graph = left["behavior_projection"], right["behavior_projection"]
                require(
                    isinstance(mapping, dict)
                    and comparison["witness"] is None
                    and comparison["correspondence_direction"] == "right_node_to_left_node"
                    and set(mapping) == {node["node_id"] for node in right_graph["nodes"]}
                    and set(mapping.values()) == {node["node_id"] for node in left_graph["nodes"]}
                    and len(mapping) == len(set(mapping.values())),
                    "panel_quotient_distribution.equivalence_bijection",
                )
                require(
                    canonical_json_bytes(domain._ordered_graph(left_graph, {}))
                    == canonical_json_bytes(domain._ordered_graph(right_graph, mapping)),
                    "panel_quotient_distribution.equivalence_correspondence_not_matching",
                )
            else:
                require(
                    comparison["correspondence"] is None
                    and isinstance(comparison["witness"], dict)
                    and bool(comparison["witness"]),
                    "panel_quotient_distribution.difference_witness_required",
                )
        by_group[comparison["task_group"]] = comparison
    return by_group


def _task_classes(
    entries: list[dict[str, Any]],
    by_qualification: dict[str, dict[str, Any]],
    comparison: dict[str, Any] | None,
    condition: dict[str, Any],
    rule: dict[str, Any],
) -> tuple[list[dict[str, Any]], list[dict[str, Any]], str]:
    valid = [entry for entry in entries if entry["qualification"]["qualified"]]
    supported = [
        entry for entry in valid if by_qualification[entry["qualification"]["id"]]["supported"]
    ]
    groups = [[entry] for entry in supported]
    reason = (
        "all_qualified_observations_assigned"
        if len(supported) == len(valid)
        else "qualified_projection_undetermined"
    )
    if len(supported) == 2:
        if comparison is None or comparison["relation"] == "undetermined":
            return (
                [],
                [],
                "supported_pair_comparison_missing"
                if comparison is None
                else "supported_pair_comparison_undetermined",
            )
        if comparison["relation"] == "equivalent":
            groups = [supported]
    classes, assignments = [], []
    for members in groups:
        representative = members[0]
        registration = representative["registration"]
        projections = [by_qualification[entry["qualification"]["id"]] for entry in members]
        proof_ids = (
            [comparison["id"]] if comparison and comparison["relation"] != "undetermined" else []
        )
        proof_basis = (
            "checked_equivalence_correspondence"
            if len(members) == 2
            else (
                "supported_projection_with_checked_separation_witness"
                if len(supported) == 2
                else "singleton_supported_observation_in_this_finite_source_bound_domain"
            )
        )
        ref = record(
            "panel_quotient_class_ref",
            measurement_condition_id=condition["id"],
            generation_condition_id=condition["generation_condition_id"],
            rule_id=rule["id"],
            **{key: registration[key] for key in TASK_FIELDS},
            finite_scope=(
                "only the explicitly bound observed qualified projections; "
                "not a universal task class identifier"
            ),
            representative_projection_id=projections[0]["id"],
            representative_qualification_id=representative["qualification"]["id"],
            member_projection_ids=[projection["id"] for projection in projections],
            member_qualification_ids=[entry["qualification"]["id"] for entry in members],
            comparison_proof_ids=proof_ids,
            relation_basis=proof_basis,
            observed_count=len(members),
            content_hash_is_relation_authority=False,
            error_count_is_class_authority=False,
            all_possible_task_classes_enumerated=False,
        )
        classes.append(ref)
        for entry, projection in zip(members, projections, strict=True):
            qualification, reg = entry["qualification"], entry["registration"]
            assignments.append(
                record(
                    "panel_quotient_assignment",
                    measurement_condition_id=condition["id"],
                    generation_condition_id=condition["generation_condition_id"],
                    rule_id=rule["id"],
                    **{key: reg[key] for key in TASK_FIELDS},
                    label=entry["label"],
                    registration_id=reg["id"],
                    registered_session_id=reg["session_id"],
                    qualification_id=qualification["id"],
                    session_id=entry["session"]["id"],
                    old_domain_audit_id=entry["audit"]["id"],
                    source_actual_graph_id=entry["graph"]["id"],
                    projection_id=projection["id"],
                    class_ref_id=ref["id"],
                    comparison_proof_ids=proof_ids,
                    relation_basis=proof_basis,
                    representative_projection_id=projections[0]["id"],
                    original_package_id=entry["package"]["id"],
                    qualified_evidence_reused_without_requalification=True,
                    old_assignment_or_projection_modified=False,
                    original_representation_modified=False,
                    formal_finite_source_bound_assignment=True,
                )
            )
    return classes, assignments, reason


def build_distribution(
    entries: list[dict[str, Any]],
    projections: list[dict[str, Any]],
    comparisons: list[dict[str, Any]],
    condition: dict[str, Any],
    rule: dict[str, Any],
) -> dict[str, Any]:
    """Bind assignments and measure q=m/2, u=n_z/2 and pi=n_z/m separately.

    All sixteen projection outcome sidecars are mandatory, including the failed
    registration's ineligible row. A supported singleton may receive a finite
    local assignment. Two supported observations need a determinate comparison;
    otherwise neither receives a fabricated singleton/difference assignment.
    Any unassigned valid mass keeps the complete task-conditional pi null.
    """
    ordered, by_qualification = _inventory(entries, projections, condition, rule)
    comparisons_by_group = _comparisons(comparisons, projections)
    classes: list[dict[str, Any]] = []
    assignments: list[dict[str, Any]] = []
    task_distributions: list[dict[str, Any]] = []
    panel_joint: list[dict[str, Any]] = []
    qualified_count = sum(entry["qualification"]["qualified"] for entry in ordered)
    for group in GROUPS:
        local = [entry for entry in ordered if entry["registration"]["task_group"] == group]
        valid = [entry for entry in local if entry["qualification"]["qualified"]]
        comparison = comparisons_by_group.get(group)
        local_classes, local_assignments, status = _task_classes(
            local,
            by_qualification,
            comparison,
            condition,
            rule,
        )
        classes.extend(local_classes)
        assignments.extend(local_assignments)
        mapped_count, valid_count = len(local_assignments), len(valid)
        unmapped_count = valid_count - mapped_count
        frequencies = [
            {
                "class_ref_id": ref["id"],
                "observed_count": ref["observed_count"],
                "joint_frequency_over_registered_sessions": _fraction(ref["observed_count"], 2),
                "qualification_ids": ref["member_qualification_ids"],
            }
            for ref in local_classes
        ]
        conditional = (
            [
                {
                    "class_ref_id": ref["id"],
                    "observed_count": ref["observed_count"],
                    "conditional_frequency": _fraction(ref["observed_count"], valid_count),
                }
                for ref in local_classes
            ]
            if valid_count and not unmapped_count
            else None
        )
        require(
            sum(ref["observed_count"] for ref in local_classes) + unmapped_count == valid_count,
            "panel_quotient_distribution.valid_mass_accounting",
        )
        task_distributions.append(
            record(
                "panel_quotient_task_distribution",
                measurement_condition_id=condition["id"],
                generation_condition_id=condition["generation_condition_id"],
                rule_id=rule["id"],
                **{key: local[0]["registration"][key] for key in TASK_FIELDS},
                design_task_marginal=_fraction(1, 8),
                registered_session_count=2,
                qualified_count=valid_count,
                known_failure_count=2 - valid_count,
                historical_success_fraction=_fraction(valid_count, 2),
                historical_success_proportion=valid_count / 2,
                original_qualification_ids=[entry["qualification"]["id"] for entry in local],
                projection_supported_qualified_count=sum(
                    by_qualification[entry["qualification"]["id"]]["supported"] for entry in valid
                ),
                assignment_count=mapped_count,
                unmapped_qualified_count=unmapped_count,
                unmapped_qualification_ids=[
                    entry["qualification"]["id"]
                    for entry in valid
                    if entry["qualification"]["id"]
                    not in {item["qualification_id"] for item in local_assignments}
                ],
                mapped_joint_mass=_fraction(mapped_count, 2),
                unmapped_joint_mass=_fraction(unmapped_count, 2),
                joint_mass_including_unmapped=_fraction(valid_count, 2),
                unmapped_mass_within_qualified=_fraction(unmapped_count, valid_count)
                if valid_count
                else None,
                class_joint_frequencies=frequencies,
                conditional_distribution=conditional,
                conditional_distribution_status=status
                if valid_count
                else "no_qualified_observations",
                complete_conditional_distribution=conditional is not None,
                observed_class_count=len(local_classes),
                observed_support_singleton=len(local_classes) == 1 and conditional is not None,
                comparison_id=comparison["id"] if comparison else None,
                comparison_relation=comparison["relation"] if comparison else None,
                expected_same_task_pairs=1 if valid_count == 2 else 0,
                success_pool_task_share=_fraction(valid_count, qualified_count),
                failed_sessions_assigned_to_valid_classes=False,
                unmapped_valid_observations_dropped_or_renormalized=False,
                empirical_frequencies_are_training_weights=False,
            )
        )
        panel_joint.extend(
            {
                "task_group": group,
                "task_id": local[0]["registration"]["task_id"],
                "class_ref_id": ref["id"],
                "weighted_joint_frequency": _fraction(ref["observed_count"], 16),
            }
            for ref in local_classes
        )
    by_assigned_qualification = {item["qualification_id"]: item for item in assignments}
    require(
        len(by_assigned_qualification) == len(assignments),
        "panel_quotient_distribution.duplicate_assignment",
    )
    assignment_status_rows = []
    for entry in ordered:
        qualification = entry["qualification"]
        assignment = by_assigned_qualification.get(qualification["id"])
        assignment_status_rows.append(
            {
                "label": entry["label"],
                "registration_id": entry["registration"]["id"],
                "qualification_id": qualification["id"],
                "session_id": entry["session"]["id"],
                "original_status": qualification["status"],
                "original_qualified": qualification["qualified"],
                "original_end_to_end_success": qualification["end_to_end_success"],
                "projection_id": by_qualification[qualification["id"]]["id"],
                "projection_status": by_qualification[qualification["id"]]["status"],
                "assignment_status": "assigned"
                if assignment
                else "valid_mapping_undetermined"
                if qualification["qualified"]
                else "ineligible_not_qualified",
                "assignment_id": assignment["id"] if assignment else None,
                "class_ref_id": assignment["class_ref_id"] if assignment else None,
            }
        )
    closed = len(assignments) == qualified_count and all(
        task["complete_conditional_distribution"] for task in task_distributions
    )
    return record(
        "panel_quotient_distribution",
        measurement_condition_id=condition["id"],
        generation_condition_id=condition["generation_condition_id"],
        rule_id=rule["id"],
        registered_task_count=8,
        registered_session_count=16,
        qualified_count=qualified_count,
        known_failure_count=16 - qualified_count,
        unknown_count=0,
        not_started_count=0,
        historical_panel_success_fraction=_fraction(qualified_count, 16),
        historical_panel_success_proportion=qualified_count / 16,
        original_qualification_ids=condition["qualification_ids"],
        original_session_ids=condition["session_ids"],
        projection_supported_qualified_count=sum(
            by_qualification[entry["qualification"]["id"]]["supported"]
            for entry in ordered
            if entry["qualification"]["qualified"]
        ),
        assignment_count=len(assignments),
        unmapped_qualified_count=qualified_count - len(assignments),
        assignments=assignments,
        classes=classes,
        task_distributions=task_distributions,
        assignment_status_rows=assignment_status_rows,
        pair_count=len(comparisons),
        expected_qualified_same_task_pairs=7,
        determinate_pair_count=sum(pair["relation"] != "undetermined" for pair in comparisons),
        panel_weighted_joint_frequencies=panel_joint,
        panel_mapped_joint_mass=_fraction(len(assignments), 16),
        panel_unmapped_joint_mass=_fraction(qualified_count - len(assignments), 16),
        panel_joint_mass_including_unmapped=_fraction(qualified_count, 16),
        complete_panel_quotient_measurement_closed=closed,
        measurement_status="closed_for_frozen_fifteen_qualified_observations"
        if closed
        else "valid_observations_remain_unmapped",
        workflow_accounting_complete=True,
        all_observed_task_supports_singleton=all(
            task["observed_support_singleton"] for task in task_distributions
        )
        if closed
        else None,
        within_task_class_reallocation_degrees_of_freedom=sum(
            max(task["observed_class_count"] - 1, 0) for task in task_distributions
        )
        if closed
        else None,
        multiple_classes_required_for_workflow_completion=False,
        class_counts_across_tasks_are_one_task_support=False,
        class_references_are_finite_source_bound_not_universal=True,
        failure_mass_entered_valid_state_distribution=False,
        historical_qualification_changed=False,
        original_projection_support_changed=False,
        source_sessions_added=0,
        original_sessions_removed=0,
        original_responses_rewritten=0,
        original_representation_modified=False,
        old_assignments_modified=False,
        task_marginal_renormalized=False,
        full_support_training_materialized=False,
        final_training_weights=None,
        class_weights_assigned=False,
        contribution_estimated=False,
        student_utility_measured=False,
        feedback_has_no_causal_effect_claimed=False,
        all_possible_task_classes_enumerated=False,
        data_blind_confirmation_claimed=False,
        old_mainline="remains_paused",
        provider_calls=0,
        runtime_executions=0,
        operation_executions=0,
        qualification_calls=0,
        tokenizer_loads=0,
        tokenizations=0,
        student_forward_calls=0,
        student_updates=0,
        gpu_jobs=0,
    )
