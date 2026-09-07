"""Three exact finite comparisons under a new, separately bound measurement layer.

The original generation condition, prompt/configuration strata, qualification and
actual-support proofs remain unchanged.  This module compares new behavior
sidecars; it does not reproduce execution, support detection or qualification.
"""

from __future__ import annotations

from typing import Any

from trusted_synthesis.canonical_json import canonical_json_bytes, strict_canonical_hash
from trusted_synthesis.domains.finance.qa_vnext import measurement as domain

from ..finance_qa_vnext_model_execution.models import identity, record, require
from ..finance_qa_vnext_panel_quotient.comparison import compare_projections

TASK_FIELDS = ("task_group", "task_type", "task_id", "context_id", "protocol_id", "registry_hash")
PAIR_LABELS = (("N03", "E04"), ("N03", "E02"), ("E02", "E04"))
VALID_LABELS = {"E02", "N03", "E04"}


def _identified(value: dict[str, Any]) -> None:
    ref = value.get("id")
    require(isinstance(ref, str) and ":" in ref, "support_transition_comparison.identity")
    assert isinstance(ref, str)
    require(
        ref
        == strict_canonical_hash(
            {key: item for key, item in value.items() if key != "id"},
            prefix=ref.split(":", 1)[0] + ":",
        ),
        "support_transition_comparison.identity",
    )


def comparison_contract(
    measurement_condition: dict[str, Any],
    generation_condition: dict[str, Any],
    rule: dict[str, Any],
) -> dict[str, Any]:
    """Bind the new rule to the old source without changing the old rule/profile IDs."""
    identity(measurement_condition, "support_transition_condition")
    identity(generation_condition, "support_exploration_condition")
    _identified(rule)
    require(
        measurement_condition["generation_condition_id"] == generation_condition["id"]
        and measurement_condition["original_generation_rule_id"] == generation_condition["rule_id"]
        and measurement_condition["rule_id"] == rule["id"]
        and rule["id"] != generation_condition["rule_id"],
        "support_transition_comparison.separate_generation_and_measurement_conditions",
    )
    require(
        rule["extends_rule_id"] == generation_condition["rule_id"],
        "support_transition_comparison.explicit_frozen_rule_extension",
    )
    require(
        generation_condition["task_group"] == "S"
        and generation_condition["task_type"] == "source_explicit_part_whole_share"
        and generation_condition["registered_session_count"] == 8
        and generation_condition["sessions_per_profile"] == 4
        and set(generation_condition["profiles"])
        == set(generation_condition["configurations"])
        == {"N", "E"},
        "support_transition_comparison.original_stratified_source",
    )
    for key in ("registration_ids", "qualification_ids", "session_ids"):
        require(
            len(measurement_condition[key]) == len(set(measurement_condition[key])) == 8,
            "support_transition_comparison.original_population",
        )
    require(
        len(measurement_condition["qualified_qualification_ids"])
        == len(set(measurement_condition["qualified_qualification_ids"]))
        == 3
        and set(measurement_condition["qualified_qualification_ids"])
        < set(measurement_condition["qualification_ids"]),
        "support_transition_comparison.original_valid_set",
    )
    profile_bindings = []
    for profile in ("N", "E"):
        publication = generation_condition["profiles"][profile]
        configuration = generation_condition["configurations"][profile]
        _identified(publication)
        _identified(configuration)
        profile_bindings.append(
            {
                "profile": profile,
                "profile_id": publication["id"],
                "model_configuration_id": configuration["id"],
            }
        )
    require(
        all(
            isinstance(measurement_condition.get(key), str) and measurement_condition[key]
            for key in (
                "old_quotient_id",
                "old_comparison_contract_id",
                "old_report_id",
                "source_anchor_id",
                "source_binding_checks_id",
                "implementation_id",
            )
        ),
        "support_transition_comparison.original_source_references",
    )
    return record(
        "support_transition_comparison_contract",
        measurement_condition_id=measurement_condition["id"],
        generation_condition_id=generation_condition["id"],
        original_generation_rule_id=generation_condition["rule_id"],
        rule_id=rule["id"],
        **{key: generation_condition[key] for key in TASK_FIELDS},
        old_quotient_id=measurement_condition["old_quotient_id"],
        old_comparison_contract_id=measurement_condition["old_comparison_contract_id"],
        source_anchor_id=measurement_condition["source_anchor_id"],
        source_binding_checks_id=measurement_condition["source_binding_checks_id"],
        profile_bindings=profile_bindings,
        original_profiles=generation_condition["profiles"],
        original_configurations=generation_condition["configurations"],
        registration_ids=measurement_condition["registration_ids"],
        qualification_ids=measurement_condition["qualification_ids"],
        session_ids=measurement_condition["session_ids"],
        qualified_qualification_ids=measurement_condition["qualified_qualification_ids"],
        registered_pairs=[
            {"left_label": left, "right_label": right} for left, right in PAIR_LABELS
        ],
        registered_pair_count=3,
        unsupported_pairs_retained=True,
        original_cross_profile_source_domain_retained=True,
        profile_name_is_behavior_label=False,
        original_generation_condition_modified=False,
        old_generation_rule_replaced=False,
        new_measurement_rule_is_separately_bound=True,
        original_parent_identity_checks_removed=False,
        behavior_equality_authority=(
            "exact nodes, final and retained_interactions under a labeled DAG correspondence"
        ),
        target_difference_authority=(
            "actual denominator role: disclosed Evidence versus accepted relation_sum Claim"
        ),
        old_actual_support_recomputed=False,
    )


def _inventory(entries, projections, measurement_condition, generation_condition, rule, contract):
    identity(contract, "support_transition_comparison_contract")
    require(
        contract == comparison_contract(measurement_condition, generation_condition, rule),
        "support_transition_comparison.frozen_contract",
    )
    labels = generation_condition["registered_labels"]
    require(
        len(entries) == len(projections) == len(labels) == len(set(labels)) == 8
        and len({entry["label"] for entry in entries}) == 8
        and {entry["label"] for entry in entries} == set(labels)
        and len({projection["label"] for projection in projections}) == 8
        and {projection["label"] for projection in projections} == set(labels)
        and len({projection["id"] for projection in projections}) == 8,
        "support_transition_comparison.exact_eight_inventory",
    )
    for field, source_key in (
        ("registration_ids", "registration"),
        ("qualification_ids", "qualification"),
        ("session_ids", "session"),
    ):
        actual = [entry[source_key]["id"] for entry in entries]
        require(
            len(actual) == len(set(actual)) == 8
            and set(actual) == set(measurement_condition[field]),
            "support_transition_comparison.frozen_population_binding",
        )
    valid = [entry for entry in entries if entry["qualification"]["qualified"] is True]
    require(
        {entry["label"] for entry in valid} == VALID_LABELS
        and {entry["qualification"]["id"] for entry in valid}
        == set(measurement_condition["qualified_qualification_ids"]),
        "support_transition_comparison.valid_set_not_promoted_or_dropped",
    )
    outcomes = {value["label"]: value for value in measurement_condition["frozen_outcomes"]}
    require(
        len(outcomes) == len(measurement_condition["frozen_outcomes"]) == 8
        and set(outcomes) == set(labels),
        "support_transition_comparison.frozen_outcomes",
    )
    by_projection = {value["label"]: value for value in projections}
    for entry in entries:
        reg, qual, session, audit, graph, old, support = (
            entry[key]
            for key in (
                "registration",
                "qualification",
                "session",
                "audit",
                "graph",
                "old_projection",
                "old_support",
            )
        )
        projection = by_projection[entry["label"]]
        identity(reg, "session_registration")
        identity(qual, "qualification")
        domain._identity(session, "session")
        domain._identity(audit, "session_audit")
        domain._identity(graph, "actual_decision_graph")
        identity(old, "panel_quotient_projection")
        identity(projection, "panel_quotient_projection")
        identity(support, "support_exploration_support")
        profile = reg["profile"]
        require(
            profile in {"N", "E"}
            and entry["label"] == reg["label"] == old["label"] == projection["label"]
            and reg["run_condition_id"] == generation_condition["id"]
            and qual["registered_session_id"] == reg["session_id"]
            and qual["registration_id"]
            == reg["id"]
            == old["registration_id"]
            == projection["registration_id"]
            == support["registration_id"]
            and qual["session_id"]
            == session["id"]
            == old["session_id"]
            == projection["session_id"]
            == support["session_id"]
            and qual["id"]
            == old["qualification_id"]
            == projection["qualification_id"]
            == support["qualification_id"]
            and qual["domain_audit_id"]
            == audit["id"]
            == old["old_domain_audit_id"]
            == projection["old_domain_audit_id"]
            and qual["domain_audit"] == audit == projection["source_domain_audit"]
            and audit["actual_decision_graph"] == graph
            and audit["finite_projection"] == entry["old_finite_projection"]
            and graph["id"]
            == old["source_actual_graph_id"]
            == projection["source_actual_graph_id"]
            == support["source_actual_graph_id"]
            and old["id"] == projection["previous_projection_id"] == support["projection_id"]
            and old["supported"] is projection["previous_projection_supported"]
            and old["old_projection_supported"]
            is projection["old_projection_supported"]
            is audit["projection_supported"]
            and support["id"] == projection["old_support_id"]
            and projection["measurement_condition_id"] == measurement_condition["id"]
            and projection["comparison_contract_id"] == contract["id"]
            and old["generation_condition_id"]
            == projection["generation_condition_id"]
            == generation_condition["id"]
            and old["rule_id"] == generation_condition["rule_id"]
            and projection["rule_id"] == rule["id"]
            and all(qual[key] == reg[key] == generation_condition[key] for key in TASK_FIELDS)
            and all(
                projection[key] == generation_condition[key]
                for key in TASK_FIELDS
                if key != "task_type"
            ),
            "support_transition_comparison.source_parent_identity",
        )
        require(
            reg["profile_id"] == generation_condition["profiles"][profile]["id"]
            and qual["model_configuration_id"]
            == reg["model_configuration_id"]
            == generation_condition["configurations"][profile]["id"]
            and all(
                value["profile"] == profile
                and value["profile_id"] == reg["profile_id"]
                and value["model_configuration_id"] == reg["model_configuration_id"]
                for value in (old, projection, support)
            ),
            "support_transition_comparison.original_profile_and_configuration",
        )
        outcome = outcomes[entry["label"]]
        require(
            outcome["registration_id"] == reg["id"]
            and outcome["qualification_id"] == qual["id"]
            and outcome["session_id"] == session["id"]
            and all(
                outcome[key] == qual[key] for key in ("qualified", "end_to_end_success", "status")
            ),
            "support_transition_comparison.outcome_not_reclassified",
        )
        if qual["qualified"] is True:
            require(
                qual["status"] == "success"
                and qual["evidence_complete"] is True
                and qual["model_origin_verified"] is True
                and support["qualified"] is True
                and support["proof_verified"] is True
                and support["support"] in {"disclosed_total", "reconstructed_total"}
                and projection["status"] in {"supported", "undetermined"}
                and projection["supported"] is (projection["status"] == "supported"),
                "support_transition_comparison.valid_projection_and_old_support",
            )
            if projection["supported"]:
                behavior = projection["behavior_projection"]
                require(
                    set(behavior) == {"nodes", "final", "retained_interactions"}
                    and canonical_json_bytes(
                        {"nodes": behavior["nodes"], "final": behavior["final"]}
                    )
                    == canonical_json_bytes(entry["old_finite_projection"]),
                    "support_transition_comparison.actual_base_semantics_changed",
                )
            if entry["label"] == "E04":
                require(
                    projection["supported"]
                    and canonical_json_bytes(projection["behavior_projection"])
                    == canonical_json_bytes(old["behavior_projection"]),
                    "support_transition_comparison.e04_supported_behavior_changed",
                )
            annotations = {row["sequence"]: row for row in projection["interpretation_ledger"]}
            for row in old["interpretation_ledger"]:
                if row["disposition"] != "undetermined":
                    require(
                        row["sequence"] in annotations
                        and annotations[row["sequence"]]["disposition"] == row["disposition"],
                        "support_transition_comparison.previous_disposition_changed",
                    )
        else:
            require(
                qual["status"] == "known_failure"
                and qual["end_to_end_success"] is False
                and projection["status"] == "ineligible"
                and projection["supported"] is False
                and projection["behavior_projection"] is None,
                "support_transition_comparison.failed_prefix_not_promoted",
            )
    return {entry["label"]: entry for entry in entries}, by_projection


def _support_view(entry):
    """Reference the original verified chain; check its preserved graph labels, not execution."""
    support, graph = entry["old_support"], entry["graph"]
    trace = support["trace"]
    nodes = {node["node_id"]: node for node in graph["nodes"]}
    require(len(nodes) == len(graph["nodes"]), "support_transition_comparison.unique_actual_nodes")
    ratio = nodes[trace["ratio"]["node_id"]]
    denominator = [ref for ref in ratio["inputs"] if ref["role"] == "denominator"]
    require(
        len(denominator) == 1
        and ratio["operation"] == trace["ratio"]["operation"] == "share_ratio"
        and denominator[0] == trace["actual_denominator"]
        and trace["actual_resolved_denominator"]["value"]["role"] == "denominator",
        "support_transition_comparison.original_denominator_proof_binding",
    )
    result = dict(
        support_record_id=support["id"],
        support=support["support"],
        source_actual_graph_id=graph["id"],
        ratio_node_id=ratio["node_id"],
        ratio_operation=ratio["operation"],
        denominator=denominator[0],
        actual_input_dependencies=ratio["input_dependencies"],
        original_verified_trace=trace,
        original_support_proof_reused_without_reexecution=True,
    )
    if support["support"] == "disclosed_total":
        require(
            denominator[0]["kind"] == "evidence"
            and denominator[0]["reference"] == {"evidence_id": trace["disclosed_total_evidence_id"]}
            and trace["actual_resolved_denominator"]["value"]["kind"] == "evidence",
            "support_transition_comparison.disclosed_evidence_label",
        )
        result["disclosed_total_evidence_id"] = trace["disclosed_total_evidence_id"]
        result["sum_producer"] = None
    else:
        total = trace["total"]
        producer = nodes[total["node_id"]]
        require(
            denominator[0]["kind"] == "claim"
            and denominator[0]["reference"] == {"producer_action": total["node_id"]}
            and producer["operation"] == total["operation"] == "relation_sum"
            and producer["node_id"] in ratio["input_dependencies"]
            and trace["accepted_total_claim_actually_consumed_by_ratio"] is True
            and trace["actual_resolved_denominator"]["value"]["kind"] == "claim"
            and trace["actual_resolved_denominator"]["ref_id"] == total["accepted_claim_id"],
            "support_transition_comparison.accepted_sum_claim_dependency_label",
        )
        result["sum_producer"] = {
            key: total[key]
            for key in (
                "node_id",
                "operation",
                "accepted_claim_id",
                "observation_id",
                "update_submission_id",
                "execution_id",
            )
        }
    return result


def compare_all(
    entries: list[dict[str, Any]],
    projections: list[dict[str, Any]],
    measurement_condition: dict[str, Any],
    generation_condition: dict[str, Any],
    rule: dict[str, Any],
    contract: dict[str, Any],
) -> list[dict[str, Any]]:
    """Keep all three preregistered pairs, including unsupported comparisons."""
    by_entry, by_projection = _inventory(
        entries, projections, measurement_condition, generation_condition, rule, contract
    )
    pairs = []
    for left_label, right_label in PAIR_LABELS:
        left, right = by_projection[left_label], by_projection[right_label]
        base = compare_projections(left, right)
        left_support, right_support = (
            _support_view(by_entry[left_label]),
            _support_view(by_entry[right_label]),
        )
        distinct = {left_support["support"], right_support["support"]} == {
            "disclosed_total",
            "reconstructed_total",
        }
        require(
            not distinct or base["relation"] != "equivalent",
            "support_transition_comparison.denominator_semantics_preservation_violation",
        )
        contrast = record(
            "support_transition_execution_support_contrast",
            measurement_condition_id=measurement_condition["id"],
            generation_condition_id=generation_condition["id"],
            rule_id=rule["id"],
            comparison_contract_id=contract["id"],
            left_support_record_id=left_support["support_record_id"],
            right_support_record_id=right_support["support_record_id"],
            left_support=left_support["support"],
            right_support=right_support["support"],
            left_qualification_id=left["qualification_id"],
            right_qualification_id=right["qualification_id"],
            left_projection_id=left["id"],
            right_projection_id=right["id"],
            left=left_support,
            right=right_support,
            verified=True,
            distinct_support_kinds=distinct,
            established=distinct
            and base["relation"] == "not_equivalent"
            and base["proof_verified"],
            decisive_input_role="denominator",
            difference_is_actual_input_kind_not_profile_or_rejection_count=distinct,
            actual_support_detection_reexecuted=False,
            claimed_rejected_proposal_was_executed=False,
        )
        pairs.append(
            record(
                "support_transition_pair",
                measurement_condition_id=measurement_condition["id"],
                generation_condition_id=generation_condition["id"],
                rule_id=rule["id"],
                comparison_contract_id=contract["id"],
                old_quotient_id=measurement_condition["old_quotient_id"],
                left_label=left_label,
                right_label=right_label,
                left_qualification_id=left["qualification_id"],
                right_qualification_id=right["qualification_id"],
                left_profile=left["profile"],
                right_profile=right["profile"],
                left_profile_id=left["profile_id"],
                right_profile_id=right["profile_id"],
                left_model_configuration_id=left["model_configuration_id"],
                right_model_configuration_id=right["model_configuration_id"],
                **{
                    key: base[key]
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
                comparison=base,
                execution_support_contrast=contrast,
                original_profile_is_behavior_label=False,
                registered_pair_preserved=True,
            )
        )
    require(len(pairs) == 3, "support_transition_comparison.complete_registered_pairs")
    return pairs
