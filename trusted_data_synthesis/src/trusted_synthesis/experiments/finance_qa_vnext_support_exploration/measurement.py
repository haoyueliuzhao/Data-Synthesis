"""Pure fixed-stratum measurement for eight newly registered Share sessions.

Prompt profiles describe the exploration source, never semantic classes. Frozen
qualifications own success, quotient sidecars own class membership, and concrete
qualified support/difference proofs own the existential dual-support witness.
Missing outcomes and unmapped valid observations remain separate kinds of mass.
"""

from __future__ import annotations

from collections import Counter
from itertools import combinations
from typing import Any

from trusted_synthesis.canonical_json import strict_canonical_hash

from ..finance_qa_vnext_model_execution.models import identity, record, require

PROFILES = ("N", "E")
STATUSES = ("success", "known_failure", "unknown", "not_started")
SUPPORTS = ("disclosed_total", "reconstructed_total", "other_or_undetermined")
TASK_FIELDS = ("task_group", "task_type", "task_id", "context_id", "protocol_id", "registry_hash")


def _fraction(numerator: int, denominator: int) -> dict[str, int]:
    require(denominator > 0, "exploration_measurement.fraction_denominator")
    return {"numerator": numerator, "denominator": denominator}


def _identified(value: dict[str, Any]) -> None:
    ref = value.get("id")
    require(isinstance(ref, str) and ":" in ref, "exploration_measurement.identity")
    assert isinstance(ref, str)
    require(
        ref
        == strict_canonical_hash(
            {key: item for key, item in value.items() if key != "id"},
            prefix=ref.split(":", 1)[0] + ":",
        ),
        "exploration_measurement.identity",
    )


def _entries(
    registrations: list[dict[str, Any]],
    entries: list[dict[str, Any]],
    condition: dict[str, Any],
) -> list[dict[str, Any]]:
    _identified(condition)
    require(
        len(registrations) == len(entries) == condition["registered_session_count"] == 8
        and condition["sessions_per_profile"] == 4,
        "exploration_measurement.fixed_denominator",
    )
    require(
        set(condition["profiles"]) == set(condition["configurations"]) == set(PROFILES)
        and condition["profile_mixture"] == {profile: _fraction(1, 2) for profile in PROFILES},
        "exploration_measurement.frozen_profile_mixture",
    )
    labels = condition["registered_labels"]
    require(
        len(labels) == len(set(labels)) == 8
        and set(labels)
        == {f"{profile}{index:02d}" for profile in PROFILES for index in range(1, 5)},
        "exploration_measurement.frozen_new_labels",
    )
    by_label = {registration["label"]: registration for registration in registrations}
    require(
        len(by_label) == 8
        and set(by_label) == set(labels)
        and len({registration["id"] for registration in registrations}) == 8
        and len({registration["session_id"] for registration in registrations}) == 8
        and Counter(registration["profile"] for registration in registrations) == {"N": 4, "E": 4},
        "exploration_measurement.registration_inventory",
    )
    by_entry_label = {entry["label"]: entry for entry in entries}
    require(
        len(by_entry_label) == 8 and set(by_entry_label) == set(labels),
        "exploration_measurement.entry_inventory",
    )
    for label in labels:
        registration = by_label[label]
        entry = by_entry_label[label]
        qualification = entry["qualification"]
        identity(registration, "session_registration")
        identity(qualification, "qualification")
        profile = registration["profile"]
        require(
            label.startswith(profile)
            and entry["registration"] == registration
            and registration["run_condition_id"] == condition["id"]
            and registration["profile_id"] == condition["profiles"][profile]["id"]
            and registration["model_configuration_id"] == condition["configurations"][profile]["id"]
            and all(registration[key] == condition[key] for key in TASK_FIELDS),
            "exploration_measurement.fresh_registration_condition",
        )
        require(
            qualification["registration_id"] == registration["id"]
            and qualification["registered_session_id"] == registration["session_id"]
            and qualification["model_configuration_id"] == registration["model_configuration_id"]
            and all(qualification[key] == registration[key] for key in TASK_FIELDS),
            "exploration_measurement.qualification_parent",
        )
        session = entry.get("session")
        require(
            qualification["session_id"] == (session["id"] if session is not None else None),
            "exploration_measurement.session_parent",
        )
        status = qualification["status"]
        require(status in STATUSES, "exploration_measurement.outcome_status")
        if status == "success":
            require(
                qualification["qualified"] is True
                and qualification["end_to_end_success"] is True
                and qualification["evidence_complete"] is True
                and qualification["model_origin_verified"] is True
                and session is not None,
                "exploration_measurement.success_evidence",
            )
        elif status == "known_failure":
            require(
                qualification["qualified"] is False
                and qualification["end_to_end_success"] is False
                and qualification["evidence_complete"] is True,
                "exploration_measurement.known_failure_evidence",
            )
        else:
            require(
                qualification["qualified"] is None and qualification["end_to_end_success"] is None,
                "exploration_measurement.missing_outcome_not_failure",
            )
        exported = entry.get("export")
        if exported is not None:
            require(
                type(exported["candidate_count"]) is int
                and exported["candidate_count"] == len(exported["rows"])
                and (qualification["qualified"] is True or not exported["rows"]),
                "exploration_measurement.positive_export_population",
            )
    require(
        len({entry["qualification"]["id"] for entry in entries}) == 8,
        "exploration_measurement.duplicate_qualification",
    )
    return [by_entry_label[label] for label in labels]


def _quotient(
    entries: list[dict[str, Any]],
    quotient: dict[str, Any],
    condition: dict[str, Any],
) -> dict[str, Any]:
    _identified(quotient)
    qualifications = {entry["qualification"]["id"]: entry["qualification"] for entry in entries}
    valid_ids = {
        qid for qid, qualification in qualifications.items() if qualification["qualified"] is True
    }
    require(
        quotient["exploration_condition_id"] == condition["id"]
        and len(quotient["qualification_ids"]) == 8
        and set(quotient["qualification_ids"]) == set(qualifications),
        "exploration_measurement.quotient_population",
    )
    projections = {
        projection["qualification_id"]: projection for projection in quotient["projections"]
    }
    supports = {row["qualification_id"]: row for row in quotient["support_rows"]}
    require(
        len(quotient["projections"]) == len(projections) == 8
        and len(quotient["support_rows"]) == len(supports) == 8
        and set(projections) == set(supports) == set(qualifications),
        "exploration_measurement.projection_support_inventory",
    )
    projection_by_id = {projection["id"]: projection for projection in quotient["projections"]}
    require(len(projection_by_id) == 8, "exploration_measurement.projection_identity_inventory")
    for entry in entries:
        reg, qual = entry["registration"], entry["qualification"]
        projection, support = projections[qual["id"]], supports[qual["id"]]
        _identified(projection)
        _identified(support)
        require(
            projection["registration_id"] == reg["id"]
            and projection["label"] == entry["label"]
            and projection["session_id"] == qual["session_id"]
            and projection["generation_condition_id"] == condition["id"]
            and projection["rule_id"] == condition["rule_id"]
            and projection["profile"] == reg["profile"]
            and projection["profile_id"] == reg["profile_id"]
            and projection["model_configuration_id"] == reg["model_configuration_id"]
            and all(projection[key] == condition[key] for key in TASK_FIELDS if key != "task_type")
            and projection["supported"] is (projection["status"] == "supported"),
            "exploration_measurement.projection_parent",
        )
        require(
            support["registration_id"] == reg["id"]
            and support["session_id"] == qual["session_id"]
            and support["projection_id"] == projection["id"]
            and support["qualified"] is qual["qualified"]
            and support["qualification_status"] == qual["status"]
            and support["profile"] == reg["profile"]
            and support["profile_id"] == reg["profile_id"]
            and support["model_configuration_id"] == reg["model_configuration_id"],
            "exploration_measurement.actual_support_parent",
        )
        if qual["qualified"] is True:
            require(
                projection["status"] in {"supported", "undetermined"}
                and support["support"] in SUPPORTS,
                "exploration_measurement.valid_support_status",
            )
            if support["support"] in {"disclosed_total", "reconstructed_total"}:
                require(
                    support["proof_verified"] is True
                    and isinstance(support["trace"], dict)
                    and bool(support["trace"]),
                    "exploration_measurement.actual_support_proof_required",
                )
        else:
            require(
                not projection["supported"] and support["support"] == "ineligible",
                "exploration_measurement.failed_or_unknown_not_positive_support",
            )
    assignments = {item["qualification_id"]: item for item in quotient["assignments"]}
    classes = {item["id"]: item for item in quotient["classes"]}
    require(
        len(assignments) == len(quotient["assignments"])
        and set(assignments) <= valid_ids
        and len(classes) == len(quotient["classes"]),
        "exploration_measurement.assignment_inventory",
    )
    for qid, assignment in assignments.items():
        _identified(assignment)
        require(
            projections[qid]["supported"]
            and assignment["projection_id"] == projections[qid]["id"]
            and assignment["class_ref_id"] in classes
            and assignment["exploration_condition_id"] == condition["id"]
            and assignment["comparison_contract_id"] == quotient["comparison_contract_id"],
            "exploration_measurement.assignment_parent",
        )
    members = []
    for ref in classes.values():
        _identified(ref)
        qids = ref["member_qualification_ids"]
        require(
            ref["exploration_condition_id"] == condition["id"]
            and ref["comparison_contract_id"] == quotient["comparison_contract_id"]
            and ref["rule_id"] == condition["rule_id"]
            and all(ref[key] == condition[key] for key in TASK_FIELDS)
            and bool(qids)
            and len(qids) == len(set(qids))
            and set(qids) <= set(assignments)
            and all(assignments[qid]["class_ref_id"] == ref["id"] for qid in qids)
            and set(ref["member_projection_ids"]) == {projections[qid]["id"] for qid in qids},
            "exploration_measurement.class_membership",
        )
        members.extend(qids)
    require(
        len(members) == len(assignments) and set(members) == set(assignments),
        "exploration_measurement.class_partition_membership",
    )
    pairs = {}
    support_witnesses, different_pairs = [], []
    require(len(quotient["pairs"]) <= 28, "exploration_measurement.pair_budget")
    for pair in quotient["pairs"]:
        _identified(pair)
        left_id, right_id = pair["left_qualification_id"], pair["right_qualification_id"]
        require(
            left_id != right_id
            and {left_id, right_id} <= valid_ids
            and pair["left_projection_id"] == projections[left_id]["id"]
            and pair["right_projection_id"] == projections[right_id]["id"],
            "exploration_measurement.pair_qualified_parents",
        )
        key = frozenset((left_id, right_id))
        require(key not in pairs, "exploration_measurement.duplicate_pair")
        comparison = pair["comparison"]
        _identified(comparison)
        require(
            pair["exploration_condition_id"] == condition["id"]
            and pair["comparison_contract_id"] == quotient["comparison_contract_id"]
            and pair["rule_id"] == condition["rule_id"]
            and comparison["generation_condition_id"] == condition["id"]
            and comparison["rule_id"] == condition["rule_id"]
            and all(comparison[key] == condition[key] for key in TASK_FIELDS if key != "task_type"),
            "exploration_measurement.cross_profile_comparison_contract",
        )
        require(
            all(
                pair[field] == comparison[field]
                for field in (
                    "left_projection_id",
                    "right_projection_id",
                    "relation",
                    "equivalent",
                    "proof_verified",
                    "witness",
                    "correspondence",
                )
            ),
            "exploration_measurement.pair_proof_binding",
        )
        relation = pair["relation"]
        require(
            relation in {"equivalent", "not_equivalent", "undetermined"}
            and pair["equivalent"]
            is {"equivalent": True, "not_equivalent": False, "undetermined": None}[relation]
            and pair["proof_verified"] is (relation != "undetermined"),
            "exploration_measurement.pair_proof_status",
        )
        if relation != "undetermined":
            require(
                projections[left_id]["supported"] and projections[right_id]["supported"],
                "exploration_measurement.proven_pair_projection_support",
            )
            if left_id in assignments and right_id in assignments:
                require(
                    (assignments[left_id]["class_ref_id"] == assignments[right_id]["class_ref_id"])
                    is (relation == "equivalent"),
                    "exploration_measurement.class_relation_proof",
                )
        if relation == "not_equivalent":
            require(
                isinstance(pair["witness"], dict) and bool(pair["witness"]),
                "exploration_measurement.retained_difference_witness",
            )
            different_pairs.append(pair["id"])
            if {supports[left_id]["support"], supports[right_id]["support"]} == {
                "disclosed_total",
                "reconstructed_total",
            }:
                disclosed = (
                    left_id if supports[left_id]["support"] == "disclosed_total" else right_id
                )
                reconstructed = right_id if disclosed == left_id else left_id
                support_witnesses.append(
                    {
                        "pair_id": pair["id"],
                        "comparison_id": comparison["id"],
                        "disclosed_qualification_id": disclosed,
                        "reconstructed_qualification_id": reconstructed,
                        "disclosed_support_record_id": supports[disclosed]["id"],
                        "reconstructed_support_record_id": supports[reconstructed]["id"],
                    }
                )
        pairs[key] = pair
    expected_pairs = {frozenset(ids) for ids in combinations(valid_ids, 2)}
    pair_closed = set(pairs) == expected_pairs and all(
        pair["relation"] != "undetermined" for pair in pairs.values()
    )
    all_valid_mapped = set(assignments) == valid_ids and pair_closed
    require(
        quotient["all_valid_mapped"] is all_valid_mapped,
        "exploration_measurement.mapping_closure_claim",
    )
    if "unmapped_qualification_ids" in quotient:
        require(
            set(quotient["unmapped_qualification_ids"]) == valid_ids - set(assignments),
            "exploration_measurement.unmapped_inventory",
        )
    witness = quotient["target_witness"]
    _identified(witness)
    require(
        witness["exploration_condition_id"] == condition["id"]
        and witness["comparison_contract_id"] == quotient["comparison_contract_id"]
        and witness["rule_id"] == condition["rule_id"]
        and set(witness["proof_pairs"]) == {item["pair_id"] for item in support_witnesses}
        and witness["established"] is bool(support_witnesses),
        "exploration_measurement.target_witness_not_profile_or_class_count",
    )
    return {
        "assignments": assignments,
        "classes": classes,
        "projections": projections,
        "supports": supports,
        "pairs": pairs,
        "all_valid_mapped": all_valid_mapped,
        "support_witnesses": sorted(support_witnesses, key=lambda row: row["pair_id"]),
        "different_pair_ids": sorted(different_pairs),
    }


def _population_summary(
    entries: list[dict[str, Any]],
    checked: dict[str, Any],
    denominator: int,
) -> dict[str, Any]:
    statuses = Counter(entry["qualification"]["status"] for entry in entries)
    valid_ids = {
        entry["qualification"]["id"]
        for entry in entries
        if entry["qualification"]["qualified"] is True
    }
    known_successes = len(valid_ids)
    missing = statuses["unknown"] + statuses["not_started"]
    complete = missing == 0
    assignments = checked["assignments"]
    assigned_ids = valid_ids & set(assignments)
    expected_pairs = {frozenset(ids) for ids in combinations(valid_ids, 2)}
    local_pairs = {key: pair for key, pair in checked["pairs"].items() if key <= valid_ids}
    pair_closed = set(local_pairs) == expected_pairs and all(
        pair["relation"] != "undetermined" for pair in local_pairs.values()
    )
    mapped = assigned_ids == valid_ids and pair_closed
    counts = Counter(assignments[qid]["class_ref_id"] for qid in assigned_ids)
    joint = [
        {
            "class_ref_id": class_id,
            "qualified_count": count,
            "observed_joint_frequency": _fraction(count, denominator),
        }
        for class_id, count in sorted(counts.items())
    ]
    observed_only = (
        [
            {
                "class_ref_id": class_id,
                "qualified_count": count,
                "conditional_frequency": _fraction(count, known_successes),
            }
            for class_id, count in sorted(counts.items())
        ]
        if known_successes and mapped
        else None
    )
    conditional = observed_only if complete else None
    require(
        len(assigned_ids)
        + (known_successes - len(assigned_ids))
        + statuses["known_failure"]
        + missing
        == denominator,
        "exploration_measurement.mass_accounting",
    )
    support_counts = Counter(checked["supports"][qid]["support"] for qid in valid_ids)
    status = (
        "outcome_population_incomplete"
        if not complete
        else "no_qualified_observations"
        if not known_successes
        else "valid_observations_or_comparisons_undetermined"
        if not mapped
        else "complete_finite_empirical_distribution"
    )
    return {
        "registered_denominator": denominator,
        **{name: statuses[name] for name in STATUSES},
        "qualified_count": known_successes,
        "known_failure_count": statuses["known_failure"],
        "outcome_population_complete": complete,
        "success_fraction": _fraction(known_successes, denominator) if complete else None,
        "success_proportion": known_successes / denominator if complete else None,
        "success_fraction_bounds": {
            "lower": _fraction(known_successes, denominator),
            "upper": _fraction(known_successes + missing, denominator),
        },
        "known_success_joint_mass": _fraction(known_successes, denominator),
        "known_failure_joint_mass": _fraction(statuses["known_failure"], denominator),
        "missing_outcome_joint_mass": _fraction(missing, denominator),
        "projection_supported_qualified_count": sum(
            checked["projections"][qid]["supported"] for qid in valid_ids
        ),
        "projection_undetermined_qualified_count": sum(
            not checked["projections"][qid]["supported"] for qid in valid_ids
        ),
        "assigned_qualified_count": len(assigned_ids),
        "unmapped_qualified_count": known_successes - len(assigned_ids),
        "mapped_valid_joint_mass": _fraction(len(assigned_ids), denominator),
        "unmapped_valid_joint_mass": _fraction(known_successes - len(assigned_ids), denominator),
        "unmapped_mass_within_observed_qualified": _fraction(
            known_successes - len(assigned_ids), known_successes
        )
        if known_successes
        else None,
        "all_observed_qualified_mapped": mapped,
        "expected_qualified_pairs": len(expected_pairs),
        "observed_qualified_pairs": len(local_pairs),
        "qualified_pair_comparison_closed": pair_closed,
        "class_joint_frequencies": joint,
        "joint_class_frequencies_complete": complete and mapped,
        "partial_joint_counts_are_only_observed_mass": not (complete and mapped),
        "conditional_distribution": conditional,
        "conditional_distribution_status": status,
        "observed_qualified_only_conditional_distribution": observed_only,
        "observed_qualified_only_scope": (
            "diagnostic conditional on the actually observed successful subset; "
            "missing outcomes not imputed"
        ),
        "conditional_population_complete": complete and mapped and known_successes > 0,
        "actual_qualified_support_counts": {
            support: support_counts[support] for support in SUPPORTS
        },
        "observed_assigned_class_count": len(counts),
        "qualification_ids": [entry["qualification"]["id"] for entry in entries],
        "bounded_zero_success_result": complete and known_successes == 0,
    }


def summarize(
    registrations: list[dict[str, Any]],
    entries: list[dict[str, Any]],
    quotient: dict[str, Any],
    condition: dict[str, Any],
) -> dict[str, Any]:
    """Measure the preregistered 4N+4E source without executing its producers."""
    ordered = _entries(registrations, entries, condition)
    checked = _quotient(ordered, quotient, condition)
    total = _population_summary(ordered, checked, 8)
    profile_rows = []
    for profile in PROFILES:
        local = [entry for entry in ordered if entry["registration"]["profile"] == profile]
        profile_rows.append(
            {
                "profile": profile,
                "profile_id": condition["profiles"][profile]["id"],
                "model_configuration_id": condition["configurations"][profile]["id"],
                "declared_profile_probability": _fraction(1, 2),
                **_population_summary(local, checked, 4),
            }
        )
    successes = total["qualified_count"]
    observed_weights = (
        {row["profile"]: _fraction(row["qualified_count"], successes) for row in profile_rows}
        if successes
        else None
    )
    session_rows = []
    for entry in ordered:
        qual, reg = entry["qualification"], entry["registration"]
        assignment = checked["assignments"].get(qual["id"])
        exported = entry.get("export")
        session_rows.append(
            {
                "label": entry["label"],
                "profile": reg["profile"],
                "profile_id": reg["profile_id"],
                "model_configuration_id": reg["model_configuration_id"],
                "registration_id": reg["id"],
                "registered_session_id": reg["session_id"],
                "session_id": qual["session_id"],
                "qualification_id": qual["id"],
                "status": qual["status"],
                "qualified": qual["qualified"],
                "end_to_end_success": qual["end_to_end_success"],
                "evidence_complete": qual["evidence_complete"],
                "projection_status": checked["projections"][qual["id"]]["status"],
                "actual_support": checked["supports"][qual["id"]]["support"],
                "assignment_id": assignment["id"] if assignment else None,
                "class_ref_id": assignment["class_ref_id"] if assignment else None,
                "depth_scope": qual.get("depth_scope"),
                "depth_metrics": qual.get("depth_metrics"),
                "provider_attempt_count": qual.get("provider_attempt_count"),
                "exported_candidate_count": exported["candidate_count"]
                if exported is not None
                else None,
            }
        )
    by_qid = {entry["qualification"]["id"]: entry["registration"]["profile"] for entry in ordered}
    class_profile_counts = [
        {
            "class_ref_id": ref["id"],
            "profile_counts": {
                profile: sum(by_qid[qid] == profile for qid in ref["member_qualification_ids"])
                for profile in PROFILES
            },
            "qualified_count": len(ref["member_qualification_ids"]),
            "exploration_joint_frequency": _fraction(len(ref["member_qualification_ids"]), 8),
        }
        for ref in sorted(checked["classes"].values(), key=lambda value: value["id"])
    ]
    return record(
        "support_exploration_measurement",
        exploration_condition_id=condition["id"],
        quotient_id=quotient["id"],
        comparison_contract_id=quotient["comparison_contract_id"],
        **{key: condition[key] for key in TASK_FIELDS},
        rule_id=condition["rule_id"],
        declared_profile_mixture=condition["profile_mixture"],
        profile_rows=profile_rows,
        session_rows=session_rows,
        class_profile_counts=class_profile_counts,
        **total,
        success_conditioned_profile_mixture=observed_weights
        if total["outcome_population_complete"]
        else None,
        observed_success_profile_mixture=observed_weights,
        success_mixture_uses_success_counts_not_fixed_half_weights=True,
        target_support_witness_established=bool(checked["support_witnesses"]),
        target_support_witnesses=checked["support_witnesses"],
        target_witness_id=quotient["target_witness"]["id"],
        at_least_two_semantically_distinct_qualified_behaviors=bool(checked["different_pair_ids"]),
        verified_not_equivalent_pair_ids=checked["different_pair_ids"],
        disclosed_support_reached=total["actual_qualified_support_counts"]["disclosed_total"] > 0,
        reconstructed_support_reached=total["actual_qualified_support_counts"][
            "reconstructed_total"
        ]
        > 0,
        support_witness_requires_all_outcomes_or_projections_resolved=False,
        profile_labels_define_classes=False,
        class_count_alone_proves_target_support=False,
        historical_model_sessions_pooled=0,
        historical_class_ids_imported=False,
        registered_sessions_replaced=0,
        missing_outcomes_counted_as_failures=False,
        unresolved_valid_observations_dropped_or_renormalized=False,
        scientific_support_witness_required_for_workflow_completion=False,
        scientific_success_count_required_for_workflow_completion=0,
        final_training_weights=None,
        profile_probabilities_are_optimal_class_weights=False,
        full_support_training_materialized=False,
        contribution_estimated=False,
        neutral_natural_preference_distribution_estimated=False,
        stable_prompt_causal_effect_claimed=False,
        autonomous_algorithm_discovery_claimed=False,
        student_utility_measured=False,
        old_panel_task_marginal_modified=False,
        provider_calls_by_measurement=0,
        runtime_executions_by_measurement=0,
        qualifier_calls_by_measurement=0,
        tokenizer_calls_by_measurement=0,
    )
