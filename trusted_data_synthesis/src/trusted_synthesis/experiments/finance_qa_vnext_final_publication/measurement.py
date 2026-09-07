"""Six new full sessions under explicit Final publication, unchanged quotient semantics."""

from __future__ import annotations

from collections import Counter
from itertools import combinations
from typing import Any

from trusted_synthesis.canonical_json import canonical_json_bytes
from trusted_synthesis.domains.finance.qa_vnext.final_public_contract import public_final_contract

from ..finance_qa_vnext_cross_binding.measurement import (
    PROFILES,
    SUPPORTS,
    TASK_FIELDS,
    _fraction,
    _identified,
    _partition,
    _support_view,
)
from ..finance_qa_vnext_model_execution.models import identity, record, require
from ..finance_qa_vnext_panel_quotient.comparison import compare_projections
from ..finance_qa_vnext_support_exploration.measurement import _population_summary
from .rules import quotient_rule


def measurement_application():
    return record(
        "final_publication_measurement_application",
        quotient_rule_id=quotient_rule()["id"],
        final_public_contract_id=public_final_contract()["id"],
        task_count=3,
        sessions_per_task=2,
        sessions_per_task_profile=1,
        maximum_pairs_per_task=1,
        maximum_same_task_pairs=3,
        unchanged_task_context_evidence_registry_and_strict_final_verifier=True,
        new_generation_has_explicit_final_schema_and_diagnostics=True,
        publication_identity_is_generation_provenance_not_behavior_label=True,
        actual_publication_must_match_frozen_contract=True,
        existing_retained_interaction_rules_reused_without_extension=True,
        new_outcome_specific_quotient_extension=False,
        qualified_out_of_domain_history_remains_undetermined=True,
        historical_sessions_or_readonly_controls_in_new_denominator=False,
        first_final_success_and_eventual_qualification_are_distinct=True,
        contemporaneous_old_presentation_control=False,
        exact_causal_improvement_claim_allowed=False,
    )


def _tasks(condition, rule):
    _identified(condition)
    _identified(rule)
    application = measurement_application()
    require(
        rule == quotient_rule()
        and condition["measurement_application_id"] == application["id"]
        and condition["final_public_contract_id"] == application["final_public_contract_id"],
        "final_measurement.frozen_application",
    )
    tasks, count = condition["tasks"], condition["task_count"]
    require(
        type(count) is int
        and count == 3
        and len(tasks) == count
        and condition["rule_id"] == rule["id"]
        and condition["registered_session_count"] == 2 * count
        and condition["sessions_per_task"] == 2
        and condition["sessions_per_task_profile"] == 1,
        "final_measurement.frozen_task_and_session_counts",
    )
    require(
        all(
            len({task[key] for task in tasks}) == count
            for key in ("task_group", "task_id", "context_id", "source_binding_id")
        )
        and all(
            isinstance(task.get(key), str) and bool(task[key])
            for task in tasks
            for key in (*TASK_FIELDS, "source_binding_id")
        ),
        "final_measurement.distinct_task_context_source_domains",
    )
    require(
        set(condition["profiles"]) == set(condition["configurations"]) == set(PROFILES)
        and condition["profile_mixture"] == {profile: _fraction(1, 2) for profile in PROFILES},
        "final_measurement.frozen_profile_mixture",
    )
    for profile in PROFILES:
        _identified(condition["profiles"][profile])
        _identified(condition["configurations"][profile])
    expected_labels = {
        f"{task['task_group']}_{profile}{repeat:02d}"
        for task in tasks
        for profile in PROFILES
        for repeat in (1,)
    }
    require(
        len(condition["registered_labels"]) == len(set(condition["registered_labels"])) == 2 * count
        and set(condition["registered_labels"]) == expected_labels,
        "final_measurement.frozen_current_labels",
    )
    marginal = {row["task_id"]: row for row in condition["task_marginal"]}
    require(
        len(condition["task_marginal"]) == len(marginal) == count
        and set(marginal) == {task["task_id"] for task in tasks}
        and all(
            marginal[task["task_id"]]
            == {
                "task_id": task["task_id"],
                "task_group": task["task_group"],
                "numerator": 1,
                "denominator": count,
            }
            for task in tasks
        ),
        "final_measurement.task_marginal_not_redefined_after_outcomes",
    )
    return tasks


def comparison_contract(condition: dict[str, Any], rule: dict[str, Any]) -> dict[str, Any]:
    """Freeze all allowed same-task domains and label pairs before model responses."""
    tasks = _tasks(condition, rule)
    permitted = []
    for task in tasks:
        labels = [
            label
            for label in condition["registered_labels"]
            if label.startswith(task["task_group"] + "_")
        ]
        for left, right in combinations(labels, 2):
            permitted.append(
                {
                    "task_id": task["task_id"],
                    "task_group": task["task_group"],
                    "left_label": left,
                    "right_label": right,
                }
            )
    return record(
        "final_publication_comparison_contract",
        measurement_application_id=condition["measurement_application_id"],
        final_public_contract_id=condition["final_public_contract_id"],
        generation_condition_id=condition["id"],
        rule_id=rule["id"],
        task_domains=tasks,
        task_count=len(tasks),
        registered_session_count=2 * len(tasks),
        registered_labels=condition["registered_labels"],
        profile_bindings=[
            {
                "profile": profile,
                "profile_id": condition["profiles"][profile]["id"],
                "model_configuration_id": condition["configurations"][profile]["id"],
            }
            for profile in PROFILES
        ],
        registered_same_task_label_pairs=permitted,
        maximum_pairs_per_task=1,
        maximum_same_task_pairs=len(tasks),
        cross_task_state_comparison_allowed=False,
        cross_profile_same_task_comparison_allowed=True,
        task_context_protocol_registry_and_rule_must_match=True,
        profile_labels_define_behavior_classes=False,
        semantic_authority=(
            "exact nodes, final, retained interactions and typed dependencies; "
            "never profile, error count or graph hash"
        ),
        support_witness_authority=(
            "same-task Qualified D/R plus determinate full comparison "
            "and verified actual denominator contrast"
        ),
        singleton_or_failed_tasks_removed_from_panel=False,
        response_dependent_rule_extension_allowed=False,
        historical_samples_or_class_ids_imported=False,
    )


def _entries(entries, projections, condition, rule, contract):
    tasks = _tasks(condition, rule)
    identity(contract, "final_publication_comparison_contract")
    require(
        contract == comparison_contract(condition, rule),
        "final_measurement.frozen_comparison_contract",
    )
    count = 2 * len(tasks)
    require(len(entries) == len(projections) == count, "final_measurement.registered_denominator")
    by_label = {entry["label"]: entry for entry in entries}
    by_qid = {entry["qualification"]["id"]: entry for entry in entries}
    by_projection = {projection["qualification_id"]: projection for projection in projections}
    require(
        len(by_label) == len(by_qid) == len(by_projection) == count
        and set(by_label) == set(condition["registered_labels"])
        and set(by_qid) == set(by_projection)
        and len({entry["registration"]["id"] for entry in entries}) == count
        and len({entry["registration"]["session_id"] for entry in entries}) == count
        and len({projection["id"] for projection in projections}) == count,
        "final_measurement.exact_current_population",
    )
    by_task = {task["task_id"]: task for task in tasks}
    counts = Counter(
        (entry["registration"]["task_id"], entry["registration"]["profile"]) for entry in entries
    )
    require(
        counts
        == Counter({(task["task_id"], profile): 1 for task in tasks for profile in PROFILES}),
        "final_measurement.one_per_task_profile",
    )
    for entry in entries:
        reg, qual, session = (entry[key] for key in ("registration", "qualification", "session"))
        identity(reg, "session_registration")
        identity(qual, "qualification")
        task = by_task[reg["task_id"]]
        profile = reg["profile"]
        require(
            entry["label"] == reg["label"]
            and entry["label"] in {f"{task['task_group']}_{profile}{repeat:02d}" for repeat in (1,)}
            and reg["run_condition_id"] == condition["id"]
            and reg["profile_id"] == condition["profiles"][profile]["id"]
            and reg["model_configuration_id"] == condition["configurations"][profile]["id"]
            and all(reg[key] == qual[key] == task[key] for key in TASK_FIELDS)
            and qual["registration_id"] == reg["id"]
            and qual["registered_session_id"] == reg["session_id"]
            and qual["model_configuration_id"] == reg["model_configuration_id"]
            and qual["session_id"] == (session["id"] if session is not None else None),
            "final_measurement.new_registration_and_qualification_parents",
        )
        status = qual["status"]
        if status == "success":
            require(
                qual["qualified"] is True
                and qual["end_to_end_success"] is True
                and qual["evidence_complete"] is True
                and qual["model_origin_verified"] is True
                and session is not None,
                "final_measurement.success_evidence",
            )
        elif status == "known_failure":
            require(
                qual["qualified"] is False
                and qual["end_to_end_success"] is False
                and qual["evidence_complete"] is True,
                "final_measurement.known_failure_evidence",
            )
        else:
            require(
                status in {"unknown", "not_started"}
                and qual["qualified"] is None
                and qual["end_to_end_success"] is None,
                "final_measurement.missing_outcomes_not_failures",
            )
        projection = by_projection[qual["id"]]
        identity(projection, "panel_quotient_projection")
        publication_binding = projection["final_publication_binding"]
        identity(publication_binding, "final_publication_projection_binding")
        require(
            publication_binding["generation_condition_id"] == condition["id"]
            and publication_binding["measurement_application_id"]
            == condition["measurement_application_id"]
            and publication_binding["public_final_contract_id"]
            == condition["final_public_contract_id"]
            and publication_binding["qualification_id"] == qual["id"]
            and publication_binding["saved_event_request_count"]
            == len(session["events"] if session else [])
            and publication_binding["quotient_semantics_changed"] is False,
            "final_measurement.actual_publication_provenance",
        )
        anchor, support = projection["base_anchor"], projection["actual_support"]
        _identified(anchor)
        identity(support, "cross_binding_support")
        audit = qual.get("domain_audit")
        graph = audit["actual_decision_graph"] if audit else None
        require(
            projection["generation_condition_id"] == condition["id"]
            and projection["rule_id"] == rule["id"]
            and projection["comparison_contract_id"] == contract["id"]
            and projection["registration_id"] == reg["id"]
            and projection["session_id"] == qual["session_id"]
            and projection["label"] == entry["label"]
            and projection["old_domain_audit_id"] == qual.get("domain_audit_id")
            and projection["source_actual_graph_id"] == (graph["id"] if graph else None)
            and all(
                projection[key] == reg[key]
                for key in (*TASK_FIELDS, "profile", "profile_id", "model_configuration_id")
            )
            and projection["supported"] is (projection["status"] == "supported"),
            "final_measurement.projection_parent",
        )
        require(
            all(
                anchor[key] == projection[key]
                for key in (
                    "generation_condition_id",
                    "rule_id",
                    "comparison_contract_id",
                    "registration_id",
                    "session_id",
                    "qualification_id",
                    "source_actual_graph_id",
                    *TASK_FIELDS,
                )
            )
            and anchor["finite_projection"] == (audit["finite_projection"] if audit else None),
            "final_measurement.actual_base_anchor",
        )
        require(
            support["base_anchor_id"] == anchor["id"]
            and support["qualification_id"] == qual["id"]
            and support["registration_id"] == reg["id"]
            and support["session_id"] == qual["session_id"]
            and support["task_id"] == task["task_id"]
            and support["context_id"] == task["context_id"]
            and support["source_actual_graph_id"] == (graph["id"] if graph else None)
            and support["qualified"] is qual["qualified"]
            and support["qualification_status"] == status,
            "final_measurement.actual_support_source_binding",
        )
        if qual["qualified"] is True:
            require(
                projection["status"] in {"supported", "undetermined"}
                and support["support"] in SUPPORTS,
                "final_measurement.valid_projection_support_separation",
            )
            if support["support"] in {"disclosed_total", "reconstructed_total"}:
                require(
                    support["proof_verified"] is True and isinstance(support["trace"], dict),
                    "final_measurement.actual_support_proof",
                )
            if projection["supported"]:
                behavior = projection["behavior_projection"]
                require(
                    set(behavior) == {"nodes", "final", "retained_interactions"}
                    and canonical_json_bytes({key: behavior[key] for key in ("nodes", "final")})
                    == canonical_json_bytes(anchor["finite_projection"]),
                    "final_measurement.actual_base_not_rewritten",
                )
        else:
            require(
                projection["status"] == "ineligible"
                and not projection["supported"]
                and support["support"] == "ineligible",
                "final_measurement.failed_or_missing_not_positive_projection",
            )
        package = entry.get("package")
        if package is not None:
            _identified(package)
            require(
                package["qualification_id"] == qual["id"]
                and package["registration_id"] == reg["id"]
                and package["session_id"] == qual["session_id"],
                "final_measurement.package_reference",
            )
        target_tokens = entry.get("target_token_count")
        require(
            target_tokens is None or type(target_tokens) is int and target_tokens >= 0,
            "final_measurement.target_token_reference_count",
        )
    return [by_label[label] for label in condition["registered_labels"]], by_projection


def compare_within_task(
    left_entry: dict[str, Any],
    right_entry: dict[str, Any],
    left: dict[str, Any],
    right: dict[str, Any],
    condition: dict[str, Any],
    rule: dict[str, Any],
    contract: dict[str, Any],
) -> dict[str, Any]:
    """A public pure comparison boundary; cross-task calls fail before graph search."""
    require(
        contract == comparison_contract(condition, rule),
        "final_measurement.comparison_contract_drift",
    )
    for entry, projection in ((left_entry, left), (right_entry, right)):
        require(
            entry["qualification"]["qualified"] is True
            and projection["qualification_id"] == entry["qualification"]["id"]
            and projection["generation_condition_id"] == condition["id"]
            and projection["rule_id"] == rule["id"]
            and projection["comparison_contract_id"] == contract["id"],
            "final_measurement.comparison_qualified_source",
        )
    require(
        left["qualification_id"] != right["qualification_id"]
        and all(left[key] == right[key] for key in TASK_FIELDS),
        "final_measurement.no_cross_task_state_comparison",
    )
    require(
        any(
            row["task_id"] == left["task_id"]
            and {row["left_label"], row["right_label"]} == {left["label"], right["label"]}
            for row in contract["registered_same_task_label_pairs"]
        ),
        "final_measurement.registered_pair_domain",
    )
    result = compare_projections(left, right)
    left_support, right_support = _support_view(left_entry, left), _support_view(right_entry, right)
    verified = left_support["verified"] and right_support["verified"]
    distinct = verified and {left_support["support"], right_support["support"]} == {
        "disclosed_total",
        "reconstructed_total",
    }
    require(
        not distinct or result["relation"] != "equivalent",
        "final_measurement.denominator_semantics_preservation",
    )
    contrast = record(
        "final_publication_execution_support_contrast",
        generation_condition_id=condition["id"],
        rule_id=rule["id"],
        comparison_contract_id=contract["id"],
        task_id=left["task_id"],
        context_id=left["context_id"],
        left_qualification_id=left["qualification_id"],
        right_qualification_id=right["qualification_id"],
        left=left_support,
        right=right_support,
        verified=verified,
        distinct_support_kinds=bool(distinct),
        established=bool(
            distinct and result["relation"] == "not_equivalent" and result["proof_verified"]
        ),
        difference_authority=(
            "actual denominator Evidence versus accepted relation_sum Claim, "
            "not profile or error count"
        ),
    )
    return record(
        "final_publication_pair",
        generation_condition_id=condition["id"],
        comparison_contract_id=contract["id"],
        rule_id=rule["id"],
        **{key: left[key] for key in TASK_FIELDS},
        left_label=left["label"],
        right_label=right["label"],
        left_qualification_id=left["qualification_id"],
        right_qualification_id=right["qualification_id"],
        left_profile=left["profile"],
        right_profile=right["profile"],
        **{
            key: result[key]
            for key in (
                "left_projection_id",
                "right_projection_id",
                "relation",
                "equivalent",
                "proof_verified",
                "correspondence",
                "witness",
            )
        },
        comparison=result,
        execution_support_contrast=contrast,
        profile_name_is_class_authority=False,
        cross_task_state_comparison=False,
    )


def analyze(
    entries: list[dict[str, Any]],
    projections: list[dict[str, Any]],
    condition: dict[str, Any],
    rule: dict[str, Any],
    contract: dict[str, Any],
) -> dict[str, Any]:
    """Compare only current same-task Qualified pairs and retain every outcome."""
    ordered, by_projection = _entries(entries, projections, condition, rule, contract)
    tasks = condition["tasks"]
    pairs, classes, assignments = [], [], []
    task_rows = []
    panel_joint: list[dict[str, Any]] = []
    for task in tasks:
        local = [entry for entry in ordered if entry["registration"]["task_id"] == task["task_id"]]
        valid = [entry for entry in local if entry["qualification"]["qualified"] is True]
        local_pairs = [
            compare_within_task(
                left,
                right,
                by_projection[left["qualification"]["id"]],
                by_projection[right["qualification"]["id"]],
                condition,
                rule,
                contract,
            )
            for left, right in combinations(valid, 2)
        ]
        require(len(local_pairs) <= 1, "final_measurement.same_task_pair_budget")
        pairs.extend(local_pairs)
        local_classes, local_assignments = _partition(
            task, local, by_projection, local_pairs, condition, rule, contract
        )
        classes.extend(local_classes)
        assignments.extend(local_assignments)
        checked = {
            "assignments": {row["qualification_id"]: row for row in local_assignments},
            "projections": by_projection,
            "supports": {
                qid: projection["actual_support"] for qid, projection in by_projection.items()
            },
            "pairs": {
                frozenset((pair["left_qualification_id"], pair["right_qualification_id"])): pair
                for pair in local_pairs
            },
        }
        summary = _population_summary(local, checked, 2)
        profile_rows = [
            {
                "profile": profile,
                "profile_id": condition["profiles"][profile]["id"],
                "model_configuration_id": condition["configurations"][profile]["id"],
                "declared_profile_probability": _fraction(1, 2),
                **_population_summary(
                    [entry for entry in local if entry["registration"]["profile"] == profile],
                    checked,
                    1,
                ),
            }
            for profile in PROFILES
        ]
        witness_pairs = [
            pair for pair in local_pairs if pair["execution_support_contrast"]["established"]
        ]
        successes = summary["qualified_count"]
        row = record(
            "final_publication_task_measurement",
            generation_condition_id=condition["id"],
            rule_id=rule["id"],
            comparison_contract_id=contract["id"],
            **task,
            **summary,
            design_task_marginal=_fraction(1, len(tasks)),
            profile_rows=profile_rows,
            success_conditioned_profile_mixture={
                profile["profile"]: _fraction(profile["qualified_count"], successes)
                for profile in profile_rows
            }
            if successes and summary["outcome_population_complete"]
            else None,
            observed_success_profile_mixture={
                profile["profile"]: _fraction(profile["qualified_count"], successes)
                for profile in profile_rows
            }
            if successes
            else None,
            W_support=bool(witness_pairs),
            target_support_witness_established=bool(witness_pairs),
            support_witness_pair_ids=[pair["id"] for pair in witness_pairs],
            support_witness_contrast_ids=[
                pair["execution_support_contrast"]["id"] for pair in witness_pairs
            ],
            determinate_pair_count=sum(pair["relation"] != "undetermined" for pair in local_pairs),
            complete_class_count=len(local_classes)
            if summary["outcome_population_complete"] and summary["all_observed_qualified_mapped"]
            else None,
            at_least_two_semantically_distinct_qualified_behaviors=any(
                pair["relation"] == "not_equivalent" for pair in local_pairs
            ),
            complete_package_count=sum(
                (entry.get("package") or {}).get("complete") is True for entry in local
            ),
            representation_reference_population_complete=all(
                entry.get("package") is not None and entry.get("target_token_count") is not None
                for entry in valid
            ),
            class_ref_ids=[ref["id"] for ref in local_classes],
        )
        task_rows.append(row)
        panel_joint.extend(
            {
                "task_id": task["task_id"],
                "task_group": task["task_group"],
                "class_ref_id": ref["id"],
                "observed_joint_frequency_over_registered_panel": _fraction(
                    len(ref["member_qualification_ids"]), 2 * len(tasks)
                ),
            }
            for ref in local_classes
        )
    require(len(pairs) <= len(tasks) <= 3, "final_measurement.total_pair_budget")
    total = len(ordered)
    successes = sum(row["qualified_count"] for row in task_rows)
    failures = sum(row["known_failure_count"] for row in task_rows)
    unknown = sum(row["unknown"] for row in task_rows)
    not_started = sum(row["not_started"] for row in task_rows)
    complete = unknown + not_started == 0
    assigned = {assignment["qualification_id"]: assignment for assignment in assignments}
    require(
        len(assigned) == len(assignments)
        and len(assignments)
        + sum(row["unmapped_qualified_count"] for row in task_rows)
        + failures
        + unknown
        + not_started
        == total,
        "final_measurement.panel_mass_accounting",
    )
    session_rows = []
    for entry in ordered:
        reg, qual = entry["registration"], entry["qualification"]
        assignment = assigned.get(qual["id"])
        projection = by_projection[qual["id"]]
        session_rows.append(
            {
                "label": entry["label"],
                "task_id": reg["task_id"],
                "task_group": reg["task_group"],
                "profile": reg["profile"],
                "profile_id": reg["profile_id"],
                "model_configuration_id": reg["model_configuration_id"],
                "registration_id": reg["id"],
                "qualification_id": qual["id"],
                "session_id": qual["session_id"],
                "status": qual["status"],
                "qualified": qual["qualified"],
                "end_to_end_success": qual["end_to_end_success"],
                "projection_id": projection["id"],
                "projection_status": projection["status"],
                "actual_support": projection["actual_support"]["support"],
                "assignment_id": assignment["id"] if assignment else None,
                "class_ref_id": assignment["class_ref_id"] if assignment else None,
                "depth_scope": qual.get("depth_scope"),
                "depth_metrics": qual.get("depth_metrics"),
                "package_id": entry["package"]["id"] if entry.get("package") else None,
                "package_complete": entry["package"]["complete"] if entry.get("package") else None,
                "target_token_count": entry.get("target_token_count"),
            }
        )
    return record(
        "final_publication_measurement",
        generation_condition_id=condition["id"],
        rule_id=rule["id"],
        comparison_contract_id=contract["id"],
        task_count=len(tasks),
        registered_session_count=total,
        task_marginal=condition["task_marginal"],
        task_rows=task_rows,
        session_rows=session_rows,
        projections=projections,
        pairs=pairs,
        classes=classes,
        assignments=assignments,
        qualified_count=successes,
        known_failure_count=failures,
        unknown_count=unknown,
        not_started_count=not_started,
        outcome_population_complete=complete,
        panel_success_fraction=_fraction(successes, total) if complete else None,
        panel_success_proportion=successes / total if complete else None,
        panel_success_fraction_bounds={
            "lower": _fraction(successes, total),
            "upper": _fraction(successes + unknown + not_started, total),
        },
        assigned_qualified_count=len(assignments),
        unmapped_qualified_count=successes - len(assignments),
        mapped_valid_joint_mass=_fraction(len(assignments), total),
        unmapped_valid_joint_mass=_fraction(successes - len(assignments), total),
        known_failure_joint_mass=_fraction(failures, total),
        missing_outcome_joint_mass=_fraction(unknown + not_started, total),
        panel_observed_task_class_joint_frequencies=panel_joint,
        panel_joint_frequencies_are_not_one_cross_task_conditional_distribution=True,
        pooled_cross_task_conditional_distribution=None,
        pair_count=len(pairs),
        maximum_same_task_pairs=len(tasks),
        cross_task_state_comparisons=0,
        tasks_with_success_witness=sum(row["qualified_count"] > 0 for row in task_rows),
        tasks_with_DR_witness=sum(row["W_support"] for row in task_rows),
        all_task_joint_frequencies_complete=all(
            row["joint_class_frequencies_complete"] for row in task_rows
        ),
        all_task_distributions_complete=all(
            row["conditional_population_complete"] for row in task_rows
        ),
        complete_conditional_distribution_task_count=sum(
            row["conditional_population_complete"] for row in task_rows
        ),
        multiple_task_bindings_present=len(tasks) > 1,
        finite_cross_binding_DR_reuse_witness=sum(row["W_support"] for row in task_rows) >= 2,
        class_ids_are_task_context_bound_not_cross_task_mechanism_labels=True,
        original_task_marginal_redefined_after_outcomes=False,
        historical_model_samples_pooled=0,
        profile_names_or_error_counts_define_classes=False,
        support_labels_alone_establish_W=False,
        W_support_required_for_workflow_completion=False,
        all_sessions_success_required=False,
        missing_outcomes_counted_as_failures=False,
        unmapped_valid_observations_renormalized_away=False,
        final_training_weights=None,
        full_support_training_materialized=False,
        contribution_estimated=False,
        student_utility_measured=False,
        blinded_evaluation_source_set_ready=False,
        generalized_financial_capability_claimed=False,
        stable_guidance_causal_effect_claimed=False,
        provider_calls_by_measurement=0,
        runtime_calls_by_measurement=0,
        qualifier_calls_by_measurement=0,
        tokenizer_calls_by_measurement=0,
        old_mainline="remains_paused",
    )
