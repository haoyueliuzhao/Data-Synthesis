"""Finite assignments and distributions for the frozen support-transition cohort.

The generation condition still names its original rule. New measurement records
bind a separate rule and comparison contract without relabeling any execution,
qualification, profile or original support proof. Only the old, condition-free
population arithmetic is reused; no old full-population mapper is invoked.
"""

from __future__ import annotations

from collections import Counter
from itertools import combinations
from typing import Any

from trusted_synthesis.canonical_json import canonical_json_bytes, strict_canonical_hash
from trusted_synthesis.domains.finance.qa_vnext import measurement as domain

from ..finance_qa_vnext_model_execution.models import identity, record, require
from ..finance_qa_vnext_support_exploration.measurement import _population_summary

PROFILES = ("N", "E")
LABELS = tuple(f"{profile}{index:02d}" for index in range(1, 5) for profile in PROFILES)
VALID_LABELS = frozenset(("N03", "E02", "E04"))
TASK_FIELDS = ("task_group", "task_type", "task_id", "context_id", "protocol_id", "registry_hash")


def _fraction(numerator: int, denominator: int) -> dict[str, int]:
    require(denominator > 0, "support_distribution.fraction_denominator")
    return {"numerator": numerator, "denominator": denominator}


def _identified(value: dict[str, Any]) -> None:
    ref = value.get("id")
    require(isinstance(ref, str) and ":" in ref, "support_distribution.record_identity")
    assert isinstance(ref, str)
    require(
        ref
        == strict_canonical_hash(
            {key: item for key, item in value.items() if key != "id"},
            prefix=ref.split(":", 1)[0] + ":",
        ),
        "support_distribution.record_identity",
    )


def _inventory(entries, projections, measurement_condition, generation_condition, rule, contract):
    for value in (measurement_condition, generation_condition, rule, contract):
        _identified(value)
    require(
        measurement_condition["generation_condition_id"] == generation_condition["id"]
        and measurement_condition["original_generation_rule_id"] == generation_condition["rule_id"]
        and measurement_condition["rule_id"] == rule["id"] != generation_condition["rule_id"]
        and contract["measurement_condition_id"] == measurement_condition["id"]
        and contract["generation_condition_id"] == generation_condition["id"]
        and contract["rule_id"] == rule["id"],
        "support_distribution.separate_measurement_and_generation",
    )
    require(
        len(entries) == len(projections) == generation_condition["registered_session_count"] == 8
        and generation_condition["sessions_per_profile"] == 4
        and tuple(generation_condition["registered_labels"]) == LABELS
        and generation_condition["profile_mixture"]
        == {profile: _fraction(1, 2) for profile in PROFILES},
        "support_distribution.frozen_eight_four_four",
    )
    for key in ("registration_ids", "qualification_ids", "session_ids"):
        require(
            len(measurement_condition[key]) == len(set(measurement_condition[key])) == 8,
            "support_distribution.frozen_identity_inventory",
        )
    valid_ids = set(measurement_condition["qualified_qualification_ids"])
    require(
        len(valid_ids) == len(measurement_condition["qualified_qualification_ids"]) == 3
        and valid_ids < set(measurement_condition["qualification_ids"]),
        "support_distribution.frozen_three_qualified",
    )
    by_label = {entry["label"]: entry for entry in entries}
    require(
        len(by_label) == 8
        and set(by_label) == set(LABELS)
        and {entry["registration"]["id"] for entry in entries}
        == set(measurement_condition["registration_ids"])
        and {entry["qualification"]["id"] for entry in entries}
        == set(measurement_condition["qualification_ids"])
        and {entry["session"]["id"] for entry in entries}
        == set(measurement_condition["session_ids"]),
        "support_distribution.no_missing_or_foreign_entry",
    )
    by_projection = {projection["qualification_id"]: projection for projection in projections}
    require(
        len(by_projection) == 8
        and set(by_projection) == set(measurement_condition["qualification_ids"])
        and len({projection["id"] for projection in projections}) == 8,
        "support_distribution.complete_projection_inventory",
    )
    if "frozen_outcomes" in measurement_condition:
        outcomes = {row["label"]: row for row in measurement_condition["frozen_outcomes"]}
        expected = {
            entry["label"]: {
                "label": entry["label"],
                "registration_id": entry["registration"]["id"],
                "qualification_id": entry["qualification"]["id"],
                "session_id": entry["session"]["id"],
                "profile": entry["registration"]["profile"],
                "profile_id": entry["registration"]["profile_id"],
                "model_configuration_id": entry["registration"]["model_configuration_id"],
                "old_projection_id": entry["old_projection"]["id"],
                "old_projection_status": entry["old_projection"]["status"],
                "old_support_id": entry["old_support"]["id"],
                "package_id": entry["package"]["id"],
                **{
                    key: entry["qualification"][key]
                    for key in ("qualified", "end_to_end_success", "status")
                },
            }
            for entry in entries
        }
        require(
            len(measurement_condition["frozen_outcomes"]) == len(outcomes) == 8
            and set(outcomes) == set(expected)
            and all(
                {
                    "label",
                    "registration_id",
                    "qualification_id",
                    "session_id",
                    "qualified",
                    "end_to_end_success",
                    "status",
                }
                <= set(row)
                <= set(expected[label])
                and all(value == expected[label][key] for key, value in row.items())
                for label, row in outcomes.items()
            ),
            "support_distribution.frozen_outcomes",
        )
    for entry in entries:
        reg, qual, session, audit, graph, old_projection, old_support, package = (
            entry[key]
            for key in (
                "registration",
                "qualification",
                "session",
                "audit",
                "graph",
                "old_projection",
                "old_support",
                "package",
            )
        )
        identity(reg, "session_registration")
        identity(qual, "qualification")
        _identified(old_projection)
        _identified(old_support)
        projection = by_projection[qual["id"]]
        _identified(projection)
        valid = qual["id"] in valid_ids
        require(
            valid is (entry["label"] in VALID_LABELS)
            and qual["qualified"] is valid
            and qual["end_to_end_success"] is valid
            and qual["status"] == ("success" if valid else "known_failure")
            and qual["evidence_complete"] is True
            and qual["model_origin_verified"] is True,
            "support_distribution.original_qualification_not_promoted",
        )
        profile = reg["profile"]
        require(
            profile in PROFILES
            and entry["label"] == reg["label"]
            and entry["label"].startswith(profile)
            and reg["run_condition_id"] == generation_condition["id"]
            and reg["profile_id"] == generation_condition["profiles"][profile]["id"]
            and reg["model_configuration_id"]
            == generation_condition["configurations"][profile]["id"]
            and qual["registration_id"] == reg["id"]
            and qual["registered_session_id"] == reg["session_id"]
            and qual["session_id"] == session["id"]
            and qual["domain_audit_id"] == audit["id"]
            and qual["domain_audit"] == audit
            and audit["actual_decision_graph"] == graph
            and audit["finite_projection"] == entry["old_finite_projection"]
            and all(reg[key] == qual[key] == generation_condition[key] for key in TASK_FIELDS),
            "support_distribution.original_source_bindings",
        )
        require(
            old_projection["qualification_id"] == qual["id"]
            and old_projection["session_id"] == session["id"]
            and old_projection["generation_condition_id"] == generation_condition["id"]
            and old_projection["rule_id"] == generation_condition["rule_id"]
            and old_support["qualification_id"] == qual["id"]
            and old_support["registration_id"] == reg["id"]
            and old_support["session_id"] == session["id"]
            and old_support["projection_id"] == old_projection["id"]
            and old_support["source_actual_graph_id"] == graph["id"]
            and old_support["qualified"] is valid
            and package["qualification_id"] == qual["id"]
            and package["session_id"] == session["id"]
            and package["registration_id"] == reg["id"],
            "support_distribution.old_sidecars_by_reference",
        )
        require(
            projection["qualification_id"] == qual["id"]
            and projection["registration_id"] == reg["id"]
            and projection["session_id"] == session["id"]
            and projection["label"] == entry["label"]
            and projection["old_domain_audit_id"] == audit["id"]
            and projection["source_actual_graph_id"] == graph["id"]
            and projection["measurement_condition_id"] == measurement_condition["id"]
            and projection["generation_condition_id"] == generation_condition["id"]
            and projection["rule_id"] == rule["id"]
            and projection["comparison_contract_id"] == contract["id"]
            and projection["previous_projection_id"] == old_projection["id"]
            and projection["previous_projection_supported"] is old_projection["supported"]
            and projection["old_support_id"] == old_support["id"]
            and all(
                projection[key] == reg[key]
                for key in ("profile", "profile_id", "model_configuration_id")
            )
            and all(
                projection[key] == generation_condition[key]
                for key in TASK_FIELDS
                if key != "task_type"
            )
            and projection["supported"] is (projection["status"] == "supported"),
            "support_distribution.new_projection_bindings",
        )
        if valid:
            require(
                projection["status"] in {"supported", "undetermined"}
                and old_support["support"] in {"disclosed_total", "reconstructed_total"}
                and old_support["proof_verified"] is True,
                "support_distribution.verified_original_support",
            )
            if projection["supported"]:
                behavior = projection["behavior_projection"]
                require(
                    isinstance(behavior, dict)
                    and set(behavior) == {"nodes", "final", "retained_interactions"}
                    and isinstance(behavior["nodes"], list)
                    and bool(behavior["nodes"])
                    and isinstance(behavior["final"], dict)
                    and isinstance(behavior["retained_interactions"], list)
                    and len({node["node_id"] for node in behavior["nodes"]})
                    == len(behavior["nodes"]),
                    "support_distribution.supported_behavior_shape",
                )
        else:
            require(
                projection["status"] == "ineligible"
                and not projection["supported"]
                and projection.get("behavior_projection") is None
                and old_support["support"] == "ineligible",
                "support_distribution.failed_prefix_not_assigned",
            )
    ordered = [by_label[label] for label in LABELS]
    require(
        Counter(entry["registration"]["profile"] for entry in ordered) == {"N": 4, "E": 4}
        and Counter(
            entry["registration"]["profile"]
            for entry in ordered
            if entry["qualification"]["qualified"]
        )
        == {"N": 1, "E": 2},
        "support_distribution.original_profile_success_counts",
    )
    return ordered, by_projection


def _contrast(
    pair, by_entry, by_projection, measurement_condition, generation_condition, rule, contract
):
    contrast = pair["execution_support_contrast"]
    _identified(contrast)
    require(
        contrast["measurement_condition_id"] == measurement_condition["id"]
        and contrast["generation_condition_id"] == generation_condition["id"]
        and contrast["comparison_contract_id"] == contract["id"]
        and contrast["rule_id"] == rule["id"]
        and contrast["verified"] is True,
        "support_distribution.execution_contrast_binding",
    )
    for side in ("left", "right"):
        qid = pair[side + "_qualification_id"]
        entry = by_entry[qid]
        old_support = entry["old_support"]
        detail = contrast[side]
        require(
            contrast[side + "_qualification_id"] == qid
            and contrast[side + "_projection_id"] == by_projection[qid]["id"]
            and contrast[side + "_support_record_id"] == old_support["id"]
            and contrast[side + "_support"] == old_support["support"]
            and detail["support_record_id"] == old_support["id"]
            and detail["support"] == old_support["support"]
            and detail["source_actual_graph_id"] == entry["graph"]["id"]
            and detail["original_verified_trace"] == old_support["trace"]
            and detail["denominator"] == old_support["trace"]["actual_denominator"]
            and detail["ratio_node_id"] == old_support["trace"]["ratio"]["node_id"]
            and detail["ratio_operation"] == "share_ratio",
            "support_distribution.execution_contrast_old_proof",
        )
        ratio = next(
            (
                node
                for node in entry["graph"]["nodes"]
                if node["node_id"] == detail["ratio_node_id"]
            ),
            None,
        )
        require(
            ratio is not None
            and detail["actual_input_dependencies"] == ratio["input_dependencies"]
            and detail["denominator"] in ratio["inputs"],
            "support_distribution.actual_denominator_not_error_count",
        )
        if old_support["support"] == "disclosed_total":
            require(
                detail["denominator"]["role"] == "denominator"
                and detail["denominator"]["kind"] == "evidence",
                "support_distribution.disclosed_evidence_denominator",
            )
        else:
            producer = detail["sum_producer"]
            source = old_support["trace"]["total"]
            require(
                detail["denominator"]["role"] == "denominator"
                and detail["denominator"]["kind"] == "claim"
                and detail["denominator"]["reference"] == {"producer_action": producer["node_id"]}
                and producer["node_id"] in detail["actual_input_dependencies"]
                and producer["operation"] == "relation_sum"
                and all(
                    producer[key] == source[key]
                    for key in (
                        "node_id",
                        "operation",
                        "accepted_claim_id",
                        "observation_id",
                        "update_submission_id",
                        "execution_id",
                    )
                ),
                "support_distribution.reconstructed_claim_production_consumption",
            )
    distinct = {contrast["left_support"], contrast["right_support"]} == {
        "disclosed_total",
        "reconstructed_total",
    }
    require(
        contrast["distinct_support_kinds"] is distinct
        and contrast["established"]
        is (distinct and pair["relation"] == "not_equivalent" and pair["proof_verified"]),
        "support_distribution.execution_contrast_result",
    )
    require(
        not distinct or pair["relation"] != "equivalent",
        "support_distribution.denominator_difference_cannot_be_equivalent",
    )
    return contrast


def _pairs(
    entries, projections, pairs, measurement_condition, generation_condition, rule, contract
):
    by_entry = {
        entry["qualification"]["id"]: entry
        for entry in entries
        if entry["qualification"]["qualified"]
    }
    expected = {frozenset(ids) for ids in combinations(by_entry, 2)}
    require(len(pairs) == 3, "support_distribution.three_pairs_must_remain_registered")
    indexed, witness_pairs = {}, []
    for pair in pairs:
        _identified(pair)
        left_id, right_id = pair["left_qualification_id"], pair["right_qualification_id"]
        key = frozenset((left_id, right_id))
        require(
            left_id != right_id and key in expected and key not in indexed,
            "support_distribution.pair_inventory",
        )
        left, right = projections[left_id], projections[right_id]
        require(
            pair["left_projection_id"] == left["id"]
            and pair["right_projection_id"] == right["id"]
            and pair["measurement_condition_id"] == measurement_condition["id"]
            and pair["generation_condition_id"] == generation_condition["id"]
            and pair["comparison_contract_id"] == contract["id"]
            and pair["rule_id"] == rule["id"],
            "support_distribution.pair_new_measurement_old_generation",
        )
        comparison = pair["comparison"]
        _identified(comparison)
        require(
            all(
                pair[key] == comparison[key]
                for key in (
                    "left_projection_id",
                    "right_projection_id",
                    "relation",
                    "equivalent",
                    "proof_verified",
                    "witness",
                    "correspondence",
                )
            )
            and comparison["generation_condition_id"] == generation_condition["id"]
            and comparison["rule_id"] == rule["id"]
            and all(
                comparison[key] == generation_condition[key]
                for key in TASK_FIELDS
                if key != "task_type"
            ),
            "support_distribution.pair_complete_proof_binding",
        )
        relation = pair["relation"]
        require(
            relation in {"equivalent", "not_equivalent", "undetermined"}
            and pair["equivalent"]
            is {"equivalent": True, "not_equivalent": False, "undetermined": None}[relation]
            and pair["proof_verified"] is (relation != "undetermined"),
            "support_distribution.pair_status",
        )
        if relation == "equivalent":
            require(
                left["supported"] and right["supported"] and pair["witness"] is None,
                "support_distribution.equivalent_supported_domain",
            )
            mapping = pair["correspondence"]
            left_graph, right_graph = left["behavior_projection"], right["behavior_projection"]
            require(
                isinstance(mapping, dict)
                and set(mapping) == {node["node_id"] for node in right_graph["nodes"]}
                and set(mapping.values()) == {node["node_id"] for node in left_graph["nodes"]}
                and len(mapping) == len(set(mapping.values())),
                "support_distribution.exact_mapping_bijection",
            )
            require(
                canonical_json_bytes(domain._ordered_graph(left_graph, {}))
                == canonical_json_bytes(domain._ordered_graph(right_graph, mapping)),
                "support_distribution.exact_mapping_full_behavior",
            )
        elif relation == "not_equivalent":
            require(
                left["supported"]
                and right["supported"]
                and pair["correspondence"] is None
                and isinstance(pair["witness"], dict)
                and bool(pair["witness"]),
                "support_distribution.retained_difference_proof",
            )
        else:
            require(
                pair["correspondence"] is None and pair["witness"] is None,
                "support_distribution.undetermined_not_forced_to_class",
            )
        contrast = _contrast(
            pair, by_entry, projections, measurement_condition, generation_condition, rule, contract
        )
        if contrast["established"]:
            witness_pairs.append(pair["id"])
        indexed[key] = pair
    require(set(indexed) == expected, "support_distribution.complete_registered_pair_set")
    return indexed, sorted(witness_pairs)


def _assignments(
    entries, projections, pairs, measurement_condition, generation_condition, rule, contract
):
    supported = {qid for qid, projection in projections.items() if projection["supported"]}
    parent = {qid: qid for qid in supported}

    def root(qid):
        while parent[qid] != qid:
            qid = parent[qid]
        return qid

    for pair in pairs.values():
        if pair["relation"] == "equivalent":
            parent[root(pair["right_qualification_id"])] = root(pair["left_qualification_id"])
    ambiguous: set[str] = set()
    for pair in pairs.values():
        left, right = pair["left_qualification_id"], pair["right_qualification_id"]
        if left not in supported or right not in supported:
            continue
        if pair["relation"] == "undetermined":
            ambiguous.update((root(left), root(right)))
        elif pair["relation"] == "not_equivalent":
            require(root(left) != root(right), "support_distribution.inconsistent_partition_proof")
    groups: dict[str, list[dict[str, Any]]] = {}
    for entry in entries:
        qid = entry["qualification"]["id"]
        if qid in supported and root(qid) not in ambiguous:
            groups.setdefault(root(qid), []).append(entry)
    classes, assignments = [], []
    common = {
        "measurement_condition_id": measurement_condition["id"],
        "generation_condition_id": generation_condition["id"],
        "original_generation_rule_id": generation_condition["rule_id"],
        "rule_id": rule["id"],
        "comparison_contract_id": contract["id"],
        **{key: generation_condition[key] for key in TASK_FIELDS},
    }
    for members in groups.values():
        qids = {entry["qualification"]["id"] for entry in members}
        inside = sorted(
            pair["id"]
            for key, pair in pairs.items()
            if key <= qids and pair["relation"] == "equivalent"
        )
        outside = sorted(
            pair["id"]
            for key, pair in pairs.items()
            if len(key & qids) == 1 and pair["relation"] == "not_equivalent"
        )
        ref = record(
            "support_transition_class_ref",
            **common,
            member_qualification_ids=[entry["qualification"]["id"] for entry in members],
            member_projection_ids=[
                projections[entry["qualification"]["id"]]["id"] for entry in members
            ],
            representative_projection_id=projections[members[0]["qualification"]["id"]]["id"],
            equivalence_pair_ids=inside,
            separation_pair_ids=outside,
            observed_count=len(members),
            profile_counts={
                profile: sum(entry["registration"]["profile"] == profile for entry in members)
                for profile in PROFILES
            },
            actual_support_counts=dict(
                sorted(Counter(entry["old_support"]["support"] for entry in members).items())
            ),
            class_authority=(
                "checked full behavior correspondences and retained difference proofs, "
                "not profile or support label alone"
            ),
            finite_source_bound_reference_not_universal_class_id=True,
            error_count_is_class_authority=False,
            profile_is_class_authority=False,
        )
        classes.append(ref)
        for entry in members:
            reg, qual = entry["registration"], entry["qualification"]
            assignments.append(
                record(
                    "support_transition_assignment",
                    **common,
                    label=entry["label"],
                    class_ref_id=ref["id"],
                    registration_id=reg["id"],
                    registered_session_id=reg["session_id"],
                    qualification_id=qual["id"],
                    session_id=entry["session"]["id"],
                    old_domain_audit_id=entry["audit"]["id"],
                    source_actual_graph_id=entry["graph"]["id"],
                    profile=reg["profile"],
                    profile_id=reg["profile_id"],
                    model_configuration_id=reg["model_configuration_id"],
                    previous_projection_id=entry["old_projection"]["id"],
                    projection_id=projections[qual["id"]]["id"],
                    old_support_proof_id=entry["old_support"]["id"],
                    original_package_id=entry["package"]["id"],
                    proof_pair_ids=inside + outside,
                    old_assignment_modified=False,
                    qualification_recomputed=False,
                    generation_condition_modified=False,
                )
            )
    require(
        len({item["qualification_id"] for item in assignments}) == len(assignments),
        "support_distribution.duplicate_assignment",
    )
    return classes, assignments


def build_distribution(
    entries: list[dict[str, Any]],
    projections: list[dict[str, Any]],
    pairs: list[dict[str, Any]],
    measurement_condition: dict[str, Any],
    generation_condition: dict[str, Any],
    rule: dict[str, Any],
    contract: dict[str, Any],
) -> dict[str, Any]:
    """Preserve 4/4 registrations and 1/2 successes; only new quotient results change."""
    ordered, by_projection = _inventory(
        entries, projections, measurement_condition, generation_condition, rule, contract
    )
    indexed_pairs, witness_pair_ids = _pairs(
        ordered, by_projection, pairs, measurement_condition, generation_condition, rule, contract
    )
    classes, assignments = _assignments(
        ordered,
        by_projection,
        indexed_pairs,
        measurement_condition,
        generation_condition,
        rule,
        contract,
    )
    by_assignment = {assignment["qualification_id"]: assignment for assignment in assignments}
    checked = {
        "assignments": by_assignment,
        "classes": {ref["id"]: ref for ref in classes},
        "projections": by_projection,
        "supports": {entry["qualification"]["id"]: entry["old_support"] for entry in ordered},
        "pairs": indexed_pairs,
    }
    # This helper only counts supplied outcomes and classes. It never receives or
    # modifies generation_condition, so its old rule identity is not retagged.
    total = _population_summary(ordered, checked, 8)
    profile_rows = [
        {
            "profile": profile,
            "profile_id": generation_condition["profiles"][profile]["id"],
            "model_configuration_id": generation_condition["configurations"][profile]["id"],
            "declared_profile_probability": _fraction(1, 2),
            **_population_summary(
                [entry for entry in ordered if entry["registration"]["profile"] == profile],
                checked,
                4,
            ),
        }
        for profile in PROFILES
    ]
    require(
        total["qualified_count"] == 3
        and total["known_failure_count"] == 5
        and total["success_fraction"] == _fraction(3, 8)
        and total["outcome_population_complete"]
        and [row["success_fraction"] for row in profile_rows] == [_fraction(1, 4), _fraction(2, 4)],
        "support_distribution.historical_success_rates_unchanged",
    )
    closed = total["conditional_population_complete"]
    statuses = []
    for entry in ordered:
        qual, reg = entry["qualification"], entry["registration"]
        assignment = by_assignment.get(qual["id"])
        statuses.append(
            {
                "label": entry["label"],
                "profile": reg["profile"],
                "registration_id": reg["id"],
                "qualification_id": qual["id"],
                "session_id": entry["session"]["id"],
                "original_status": qual["status"],
                "original_qualified": qual["qualified"],
                "original_end_to_end_success": qual["end_to_end_success"],
                "previous_projection_id": entry["old_projection"]["id"],
                "previous_projection_supported": entry["old_projection"]["supported"],
                "new_projection_id": by_projection[qual["id"]]["id"],
                "new_projection_status": by_projection[qual["id"]]["status"],
                "actual_support": entry["old_support"]["support"],
                "assignment_id": assignment["id"] if assignment else None,
                "class_ref_id": assignment["class_ref_id"] if assignment else None,
                "assignment_status": "assigned"
                if assignment
                else "valid_mapping_undetermined"
                if qual["qualified"]
                else "ineligible_not_qualified",
            }
        )
    target = record(
        "support_transition_target_witness",
        measurement_condition_id=measurement_condition["id"],
        generation_condition_id=generation_condition["id"],
        rule_id=rule["id"],
        comparison_contract_id=contract["id"],
        established=bool(witness_pair_ids),
        proof_pair_ids=witness_pair_ids,
        execution_support_contrast_ids=sorted(
            pair["execution_support_contrast"]["id"]
            for pair in pairs
            if pair["id"] in witness_pair_ids
        ),
        independent_of_unrelated_unmapped_valid_observations=True,
        support_type_labels_without_verified_denominator_difference_are_insufficient=True,
        historical_target_witness_rewritten=False,
    )
    return record(
        "support_transition_distribution",
        measurement_condition_id=measurement_condition["id"],
        generation_condition_id=generation_condition["id"],
        original_generation_rule_id=generation_condition["rule_id"],
        rule_id=rule["id"],
        comparison_contract_id=contract["id"],
        **{key: generation_condition[key] for key in TASK_FIELDS},
        **total,
        declared_profile_mixture=generation_condition["profile_mixture"],
        profile_rows=profile_rows,
        success_conditioned_profile_mixture={
            row["profile"]: _fraction(row["qualified_count"], 3) for row in profile_rows
        },
        assignments=assignments,
        classes=classes,
        assignment_status_rows=statuses,
        assignment_count=len(assignments),
        registered_pair_count=len(pairs),
        determinate_pair_count=sum(pair["relation"] != "undetermined" for pair in pairs),
        pair_ids=[pair["id"] for pair in pairs],
        target_support_witness=target,
        target_support_witness_established=target["established"],
        W_support=target["established"],
        all_valid_mapped=closed,
        complete_quotient_measurement_closed=closed,
        complete_class_count=len(classes) if closed else None,
        within_observed_class_reallocation_degrees_of_freedom=max(len(classes) - 1, 0)
        if closed
        else None,
        measurement_status="closed_for_frozen_three_qualified_observations"
        if closed
        else "valid_observations_or_comparisons_remain_undetermined",
        all_original_eight_outcomes_preserved=True,
        historical_qualified_count=3,
        old_qualification_recomputed=False,
        old_generation_condition_modified=False,
        old_projection_or_assignment_modified=False,
        historical_target_witness_rewritten=False,
        original_candidate_or_token_records_modified=False,
        original_packages_modified=False,
        profile_names_or_error_counts_define_classes=False,
        success_conditioned_mixture_uses_success_counts_not_fixed_halves=True,
        target_witness_requires_full_distribution_closure=False,
        final_training_weights=None,
        class_weights_assigned=False,
        contribution_estimated=False,
        student_utility_measured=False,
        data_blind_confirmation_claimed=False,
        generalization_or_guidance_causal_effect_claimed=False,
        full_support_training_materialized=False,
        old_mainline="remains_paused",
        provider_calls=0,
        runtime_executions=0,
        operation_executions=0,
        qualifier_calls=0,
        tokenizations=0,
        student_forward_calls=0,
        student_updates=0,
        gpu_jobs=0,
    )
