"""New-only constructed controls for frozen-cohort distribution measurement.

These artificial records are not model samples. The tests use the new pure
comparison API over constructed graphs, never old qualification, execution,
support extraction, tokenizer, or historical artifact loading.
"""

from __future__ import annotations

import copy
import socket

import pytest

from trusted_synthesis.canonical_json import canonical_json_bytes
from trusted_synthesis.domains.finance.qa_vnext import measurement as domain
from trusted_synthesis.domains.finance.qa_vnext.protocol import ProtocolError
from trusted_synthesis.domains.finance.qa_vnext.protocol import record as public_record
from trusted_synthesis.domains.finance.qa_vnext.runtime import PublicQARuntime
from trusted_synthesis.experiments.finance_qa_vnext_model_execution import qualification
from trusted_synthesis.experiments.finance_qa_vnext_model_execution.models import record
from trusted_synthesis.experiments.finance_qa_vnext_model_execution.transport import HttpxSender
from trusted_synthesis.experiments.finance_qa_vnext_support_exploration import quotient as previous
from trusted_synthesis.experiments.finance_qa_vnext_support_transition.comparison import (
    compare_all,
    comparison_contract,
)
from trusted_synthesis.experiments.finance_qa_vnext_support_transition.distribution import (
    LABELS,
    TASK_FIELDS,
    VALID_LABELS,
    build_distribution,
)


def forbidden(*args, **kwargs):
    pytest.fail("constructed distribution controls may not execute a historical producer")


@pytest.fixture(autouse=True)
def no_producers(monkeypatch):
    monkeypatch.setattr(socket.socket, "connect", forbidden)
    monkeypatch.setattr(socket, "create_connection", forbidden)
    monkeypatch.setattr(PublicQARuntime, "run", forbidden)
    monkeypatch.setattr(HttpxSender, "send", forbidden)
    monkeypatch.setattr(qualification, "qualify_session", forbidden)
    monkeypatch.setattr(domain, "audit_session", forbidden)
    monkeypatch.setattr(domain, "compare_sessions", forbidden)
    monkeypatch.setattr(previous, "actual_support", forbidden)


def rerecord(value, kind, **changes):
    fields = {
        key: copy.deepcopy(item)
        for key, item in value.items()
        if key not in {"id", "schema_version"}
    }
    fields.update(changes)
    return record(kind, **fields)


def _constructed_graph(label, reconstructed):
    sum_id, ratio_id, percent_id = (f"{label}:{name}" for name in ("sum", "ratio", "percent"))
    denominator = {
        "role": "denominator",
        "kind": "claim" if reconstructed else "evidence",
        "reference": {"producer_action": sum_id}
        if reconstructed
        else {"evidence_id": "constructed_total"},
    }
    nodes = [
        {
            "node_id": sum_id,
            "operation": "relation_sum",
            "inputs": [
                {
                    "role": "member",
                    "kind": "evidence",
                    "reference": {"evidence_id": "constructed_freight"},
                },
                {
                    "role": "member",
                    "kind": "evidence",
                    "reference": {"evidence_id": "constructed_other"},
                },
                {
                    "role": "relation",
                    "kind": "evidence",
                    "reference": {"evidence_id": "constructed_relation"},
                },
            ],
            "input_dependencies": [],
            "decision_dependencies": [],
        },
        {
            "node_id": ratio_id,
            "operation": "share_ratio",
            "inputs": [
                {
                    "role": "numerator",
                    "kind": "evidence",
                    "reference": {"evidence_id": "constructed_freight"},
                },
                denominator,
            ],
            "input_dependencies": [sum_id] if reconstructed else [],
            "decision_dependencies": [sum_id] if reconstructed else [],
        },
        {
            "node_id": percent_id,
            "operation": "scale_percent",
            "inputs": [
                {"role": "ratio", "kind": "claim", "reference": {"producer_action": ratio_id}},
            ],
            "input_dependencies": [ratio_id],
            "decision_dependencies": [ratio_id],
        },
    ]
    total_trace = {
        "node_id": sum_id,
        "operation": "relation_sum",
        "accepted_claim_id": label + ":total_claim",
        "observation_id": label + ":sum_observation",
        "update_submission_id": label + ":sum_update",
        "execution_id": label + ":sum_execution",
    }
    trace = {
        "ratio": {"node_id": ratio_id, "operation": "share_ratio"},
        "percent": {"node_id": percent_id, "operation": "scale_percent"},
        "actual_denominator": denominator,
        "actual_resolved_denominator": {
            "ref_id": total_trace["accepted_claim_id"] if reconstructed else "constructed_total",
            "value": {"role": "denominator", "kind": "claim" if reconstructed else "evidence"},
        },
    }
    if reconstructed:
        trace.update(total=total_trace, accepted_total_claim_actually_consumed_by_ratio=True)
    else:
        trace["disclosed_total_evidence_id"] = "constructed_total"
    final = {
        "answer_producer": {"producer_action": percent_id},
        "result": {"value": "93.508458", "unit": "percent"},
        "citations": ["constructed_freight", "constructed_other", "constructed_relation"]
        if reconstructed
        else ["constructed_freight", "constructed_total"],
    }
    return nodes, final, trace


def constructed_source(*, split_reconstructed=False, unsupported=()):
    old_rule = record("constructed_old_rule", control_evidence=True)
    rule = record("support_transition_rule", extends_rule_id=old_rule["id"], control_evidence=True)
    profiles = {
        name: record("constructed_profile", profile=name, control_evidence=True)
        for name in ("N", "E")
    }
    configs = {
        name: record("constructed_configuration", profile=name, control_evidence=True)
        for name in ("N", "E")
    }
    generation = record(
        "support_exploration_condition",
        task_group="S",
        task_type="source_explicit_part_whole_share",
        task_id="constructed_share_task",
        context_id="constructed_context",
        protocol_id="constructed_protocol",
        registry_hash="constructed_registry",
        rule_id=old_rule["id"],
        profiles=profiles,
        configurations=configs,
        registered_session_count=8,
        sessions_per_profile=4,
        registered_labels=list(LABELS),
        profile_mixture={name: {"numerator": 1, "denominator": 2} for name in ("N", "E")},
        control_evidence=True,
    )
    entries = []
    for label in LABELS:
        profile, valid = label[0], label in VALID_LABELS
        reconstructed = label in {"N03", "E02"}
        nodes, final, trace = _constructed_graph(label, reconstructed)
        base = {"nodes": nodes, "final": final if valid else None}
        graph = public_record("actual_decision_graph", nodes=nodes, control_evidence=True)
        session = public_record("session", constructed_label=label, control_evidence=True)
        audit = public_record(
            "session_audit",
            session_id=session["id"],
            actual_decision_graph=graph,
            finite_projection=base,
            projection_supported=False,
            control_evidence=True,
        )
        reg = record(
            "session_registration",
            label=label,
            profile=profile,
            profile_id=profiles[profile]["id"],
            model_configuration_id=configs[profile]["id"],
            run_condition_id=generation["id"],
            session_id="constructed_registered_" + label,
            **{key: generation[key] for key in TASK_FIELDS},
            control_evidence=True,
        )
        qual = record(
            "qualification",
            registration_id=reg["id"],
            registered_session_id=reg["session_id"],
            session_id=session["id"],
            domain_audit_id=audit["id"],
            domain_audit=audit,
            model_configuration_id=reg["model_configuration_id"],
            **{key: generation[key] for key in TASK_FIELDS},
            qualified=valid,
            end_to_end_success=valid,
            status="success" if valid else "known_failure",
            evidence_complete=True,
            model_origin_verified=True,
            control_evidence=True,
        )
        old_supported = label == "E04"
        old_projection = record(
            "panel_quotient_projection",
            label=label,
            registration_id=reg["id"],
            qualification_id=qual["id"],
            session_id=session["id"],
            old_domain_audit_id=audit["id"],
            source_actual_graph_id=graph["id"],
            generation_condition_id=generation["id"],
            rule_id=old_rule["id"],
            **{key: generation[key] for key in TASK_FIELDS if key != "task_type"},
            profile=profile,
            profile_id=reg["profile_id"],
            model_configuration_id=reg["model_configuration_id"],
            old_projection_supported=False,
            supported=old_supported,
            status="supported" if old_supported else "undetermined" if valid else "ineligible",
            behavior_projection={**base, "retained_interactions": []} if old_supported else None,
            interpretation_ledger=[],
            control_evidence=True,
        )
        support = record(
            "support_exploration_support",
            label=label,
            registration_id=reg["id"],
            qualification_id=qual["id"],
            session_id=session["id"],
            projection_id=old_projection["id"],
            source_actual_graph_id=graph["id"],
            profile=profile,
            profile_id=reg["profile_id"],
            model_configuration_id=reg["model_configuration_id"],
            qualified=valid,
            support="reconstructed_total"
            if reconstructed
            else "disclosed_total"
            if valid
            else "ineligible",
            proof_verified=valid,
            trace=trace if valid else None,
            control_evidence=True,
        )
        package = record(
            "task_panel_session_package",
            registration_id=reg["id"],
            qualification_id=qual["id"],
            session_id=session["id"],
            complete=valid,
            control_evidence=True,
        )
        entries.append(
            {
                "label": label,
                "registration": reg,
                "qualification": qual,
                "session": session,
                "audit": audit,
                "graph": graph,
                "old_projection": old_projection,
                "old_finite_projection": base,
                "old_support": support,
                "package": package,
            }
        )
    measurement = record(
        "support_transition_condition",
        generation_condition_id=generation["id"],
        original_generation_rule_id=old_rule["id"],
        rule_id=rule["id"],
        registration_ids=[entry["registration"]["id"] for entry in entries],
        qualification_ids=[entry["qualification"]["id"] for entry in entries],
        session_ids=[entry["session"]["id"] for entry in entries],
        qualified_qualification_ids=[
            entry["qualification"]["id"] for entry in entries if entry["qualification"]["qualified"]
        ],
        frozen_outcomes=[
            {
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
        ],
        **{
            key: "constructed_" + key
            for key in (
                "old_quotient_id",
                "old_comparison_contract_id",
                "old_report_id",
                "source_anchor_id",
                "source_binding_checks_id",
                "implementation_id",
            )
        },
        control_evidence=True,
    )
    contract = comparison_contract(measurement, generation, rule)
    projections = []
    for entry in entries:
        label, valid = entry["label"], entry["qualification"]["qualified"]
        supported = valid and label not in unsupported
        retained = []
        if label in {"N03", "E02"}:
            retained = [
                {
                    "kind": "constructed_support_transition",
                    "sum": {"producer_action": label + ":sum"},
                    "ratio": {"producer_action": label + ":ratio"},
                }
            ]
        if label == "E02" and split_reconstructed:
            retained.append(
                {
                    "kind": "constructed_support_assertion_sequence",
                    "states": ["incorrect", "aligned"],
                }
            )
        projections.append(
            rerecord(
                entry["old_projection"],
                "panel_quotient_projection",
                rule_id=rule["id"],
                measurement_condition_id=measurement["id"],
                comparison_contract_id=contract["id"],
                previous_projection_id=entry["old_projection"]["id"],
                previous_projection_supported=entry["old_projection"]["supported"],
                old_support_id=entry["old_support"]["id"],
                source_domain_audit=entry["audit"],
                supported=supported,
                status="supported" if supported else "undetermined" if valid else "ineligible",
                behavior_projection={
                    **entry["old_finite_projection"],
                    "retained_interactions": retained,
                }
                if supported
                else None,
            )
        )
    pairs = compare_all(entries, projections, measurement, generation, rule, contract)
    return {
        "entries": entries,
        "projections": projections,
        "pairs": pairs,
        "measurement_condition": measurement,
        "generation_condition": generation,
        "rule": rule,
        "contract": contract,
    }


def profile(result, name):
    return next(row for row in result["profile_rows"] if row["profile"] == name)


def test_three_assignments_and_two_classes_follow_actual_comparison_not_profile():
    source = constructed_source()
    result = build_distribution(**source)
    assert result["assignment_count"] == 3 and result["complete_class_count"] == 2
    assert result["complete_quotient_measurement_closed"] and result["W_support"]
    assert result["registered_pair_count"] == result["expected_qualified_pairs"] == 3
    assert result["determinate_pair_count"] == 3
    assignments = {row["label"]: row for row in result["assignments"]}
    assert assignments["N03"]["class_ref_id"] == assignments["E02"]["class_ref_id"]
    assert assignments["E02"]["class_ref_id"] != assignments["E04"]["class_ref_id"]
    assert assignments["N03"]["profile"] != assignments["E02"]["profile"]
    assert assignments["E02"]["profile"] == assignments["E04"]["profile"]
    assert not result["profile_names_or_error_counts_define_classes"]
    assert sorted(
        row["conditional_frequency"]["numerator"] for row in result["conditional_distribution"]
    ) == [1, 2]
    assert all(
        row["conditional_frequency"]["denominator"] == 3
        for row in result["conditional_distribution"]
    )
    assert len(result["target_support_witness"]["proof_pair_ids"]) == 2


def test_additional_retained_assertion_sequence_can_produce_three_classes():
    result = build_distribution(**constructed_source(split_reconstructed=True))
    assert result["complete_class_count"] == 3 and result["assignment_count"] == 3
    assert result["within_observed_class_reallocation_degrees_of_freedom"] == 2
    assert result["W_support"] and result["complete_quotient_measurement_closed"]
    assert all(
        row["conditional_frequency"] == {"numerator": 1, "denominator": 3}
        for row in result["conditional_distribution"]
    )
    assert not result["contribution_estimated"] and result["final_training_weights"] is None


def test_q_u_pi_and_success_conditioned_profile_weights_preserve_distinct_denominators():
    result = build_distribution(**constructed_source())
    assert result["registered_denominator"] == 8 and result["qualified_count"] == 3
    assert result["known_failure_count"] == 5 and result["success_fraction"] == {
        "numerator": 3,
        "denominator": 8,
    }
    assert profile(result, "N")["success_fraction"] == {"numerator": 1, "denominator": 4}
    assert profile(result, "E")["success_fraction"] == {"numerator": 2, "denominator": 4}
    assert profile(result, "N")["conditional_distribution"][0]["conditional_frequency"] == {
        "numerator": 1,
        "denominator": 1,
    }
    assert all(
        row["conditional_frequency"] == {"numerator": 1, "denominator": 2}
        for row in profile(result, "E")["conditional_distribution"]
    )
    assert (
        sum(
            row["observed_joint_frequency"]["numerator"]
            for row in result["class_joint_frequencies"]
        )
        == 3
    )
    assert all(
        row["observed_joint_frequency"]["denominator"] == 8
        for row in result["class_joint_frequencies"]
    )
    assert result["success_conditioned_profile_mixture"] == {
        "N": {"numerator": 1, "denominator": 3},
        "E": {"numerator": 2, "denominator": 3},
    }
    assert result["declared_profile_mixture"] == {
        name: {"numerator": 1, "denominator": 2} for name in ("N", "E")
    }


def test_concrete_dr_witness_does_not_require_e02_mapping_or_full_pi():
    result = build_distribution(**constructed_source(unsupported=("E02",)))
    assert result["registered_pair_count"] == 3 and result["determinate_pair_count"] == 1
    assert result["assignment_count"] == 2 and result["unmapped_qualified_count"] == 1
    assert result["W_support"] and not result["complete_quotient_measurement_closed"]
    assert result["complete_class_count"] is result["conditional_distribution"] is None
    assert result["mapped_valid_joint_mass"] == {"numerator": 2, "denominator": 8}
    assert result["unmapped_valid_joint_mass"] == {"numerator": 1, "denominator": 8}
    assert result["known_failure_joint_mass"] == {"numerator": 5, "denominator": 8}
    assert result["success_fraction"] == {"numerator": 3, "denominator": 8}
    assert profile(result, "N")["conditional_distribution"] is not None
    assert profile(result, "E")["conditional_distribution"] is None


def test_actual_r_support_alone_does_not_force_w_or_renormalize_only_disclosed_assignment():
    result = build_distribution(**constructed_source(unsupported=("N03", "E02")))
    assert result["actual_qualified_support_counts"]["reconstructed_total"] == 2
    assert result["actual_qualified_support_counts"]["disclosed_total"] == 1
    assert result["assignment_count"] == 1 and result["unmapped_qualified_count"] == 2
    assert not result["W_support"] and result["conditional_distribution"] is None
    assert result["complete_class_count"] is None
    assert result["registered_pair_count"] == 3 and result["determinate_pair_count"] == 0
    assert result["mapped_valid_joint_mass"] == {"numerator": 1, "denominator": 8}
    assert result["unmapped_valid_joint_mass"] == {"numerator": 2, "denominator": 8}


def test_five_failures_stay_unassigned_while_successes_keep_original_parent_refs():
    source = constructed_source()
    result = build_distribution(**source)
    by_label = {entry["label"]: entry for entry in source["entries"]}
    failures = [row for row in result["assignment_status_rows"] if not row["original_qualified"]]
    assert len(failures) == 5 and len(result["assignment_status_rows"]) == 8
    assert all(row["assignment_id"] is None and row["class_ref_id"] is None for row in failures)
    for assignment in result["assignments"]:
        original = by_label[assignment["label"]]
        assert assignment["label"] in VALID_LABELS
        assert assignment["qualification_id"] == original["qualification"]["id"]
        assert assignment["source_actual_graph_id"] == original["graph"]["id"]
        assert assignment["old_support_proof_id"] == original["old_support"]["id"]
        assert assignment["original_package_id"] == original["package"]["id"]
        assert assignment["profile_id"] == original["registration"]["profile_id"]
        assert (
            assignment["model_configuration_id"]
            == original["registration"]["model_configuration_id"]
        )
        assert assignment["generation_condition_id"] == source["generation_condition"]["id"]
        assert (
            assignment["original_generation_rule_id"] == source["generation_condition"]["rule_id"]
        )
        assert assignment["rule_id"] == source["rule"]["id"]


@pytest.mark.parametrize(
    "mutation",
    [
        "missing_valid",
        "missing_projection",
        "missing_pair",
        "duplicate_entry",
        "shrunken_condition",
    ],
)
def test_missing_valid_data_or_pair_cannot_shrink_the_frozen_population(mutation):
    source = constructed_source()
    if mutation == "missing_valid":
        source["entries"] = [entry for entry in source["entries"] if entry["label"] != "E02"]
    elif mutation == "missing_projection":
        source["projections"] = [row for row in source["projections"] if row["label"] != "E02"]
    elif mutation == "missing_pair":
        source["pairs"].pop()
    elif mutation == "duplicate_entry":
        source["entries"][-1] = source["entries"][0]
    else:
        source["measurement_condition"] = rerecord(
            source["measurement_condition"],
            "support_transition_condition",
            qualification_ids=source["measurement_condition"]["qualification_ids"][:-1],
        )
    with pytest.raises(ProtocolError, match="support_distribution"):
        build_distribution(**source)


def test_failed_prefix_promotion_to_supported_is_rejected():
    source = constructed_source()
    valid = next(row for row in source["projections"] if row["label"] == "E04")
    source["projections"][0] = rerecord(
        source["projections"][0],
        "panel_quotient_projection",
        status="supported",
        supported=True,
        behavior_projection=valid["behavior_projection"],
    )
    with pytest.raises(ProtocolError, match="failed_prefix_not_assigned"):
        build_distribution(**source)


def test_original_generation_rule_is_never_replaced_to_fake_cross_rule_compatibility():
    source = constructed_source()
    before = canonical_json_bytes(source["generation_condition"])
    result = build_distribution(**source)
    assert canonical_json_bytes(source["generation_condition"]) == before
    assert result["original_generation_rule_id"] != result["rule_id"]
    assert not result["old_generation_condition_modified"]
    source["generation_condition"] = rerecord(
        source["generation_condition"],
        "support_exploration_condition",
        rule_id=source["rule"]["id"],
    )
    with pytest.raises(ProtocolError, match="separate_measurement_and_generation"):
        build_distribution(**source)


def test_forged_denominator_contrast_cannot_turn_error_count_into_witness():
    source = constructed_source()
    pair = source["pairs"][0]
    contrast = pair["execution_support_contrast"]
    left = copy.deepcopy(contrast["left"])
    left["denominator"] = {
        "role": "denominator",
        "kind": "evidence",
        "reference": {"evidence_id": "fake_total"},
    }
    forged = rerecord(contrast, "support_transition_execution_support_contrast", left=left)
    source["pairs"][0] = rerecord(
        pair, "support_transition_pair", execution_support_contrast=forged
    )
    with pytest.raises(ProtocolError, match="execution_contrast_old_proof"):
        build_distribution(**source)


def test_unverified_pair_cannot_authorize_formal_assignment_or_witness():
    source = constructed_source()
    pair = source["pairs"][0]
    comparison = rerecord(pair["comparison"], "panel_quotient_comparison", proof_verified=False)
    source["pairs"][0] = rerecord(
        pair, "support_transition_pair", comparison=comparison, proof_verified=False
    )
    with pytest.raises(ProtocolError, match="pair_status"):
        build_distribution(**source)


def test_equivalence_mapping_is_checked_without_new_search_and_inputs_unchanged(monkeypatch):
    source = constructed_source()
    before = canonical_json_bytes(source)
    monkeypatch.setattr(domain, "_isomorphism", forbidden)
    expected = build_distribution(**source)
    assert canonical_json_bytes(source) == before
    source["entries"].reverse()
    source["projections"].reverse()
    assert build_distribution(**source) == expected
    assert (
        expected["provider_calls"]
        == expected["runtime_executions"]
        == expected["qualifier_calls"]
        == 0
    )
    assert (
        expected["tokenizations"] == expected["student_forward_calls"] == expected["gpu_jobs"] == 0
    )
    assert not expected["historical_target_witness_rewritten"]


def test_equivalence_flag_with_wrong_node_correspondence_is_rejected():
    source = constructed_source()
    index = next(
        index for index, row in enumerate(source["pairs"]) if row["relation"] == "equivalent"
    )
    pair = source["pairs"][index]
    comparison = rerecord(
        pair["comparison"], "panel_quotient_comparison", correspondence={"wrong": "wrong"}
    )
    source["pairs"][index] = rerecord(
        pair, "support_transition_pair", comparison=comparison, correspondence={"wrong": "wrong"}
    )
    with pytest.raises(ProtocolError, match="exact_mapping_bijection"):
        build_distribution(**source)


def test_enriched_frozen_outcome_source_reference_is_checked_not_ignored():
    source = constructed_source()
    outcomes = copy.deepcopy(source["measurement_condition"]["frozen_outcomes"])
    next(row for row in outcomes if row["label"] == "N03")["old_support_id"] = (
        "other_support_record"
    )
    changed = rerecord(
        source["measurement_condition"], "support_transition_condition", frozen_outcomes=outcomes
    )
    source["measurement_condition"] = changed
    source["contract"] = comparison_contract(
        changed, source["generation_condition"], source["rule"]
    )
    with pytest.raises(ProtocolError, match="frozen_outcomes"):
        build_distribution(**source)


def test_undetermined_supported_rr_pair_does_not_erase_independent_dr_witness():
    source = constructed_source()
    index = next(
        index for index, pair in enumerate(source["pairs"]) if pair["relation"] == "equivalent"
    )
    pair = source["pairs"][index]
    comparison = rerecord(
        pair["comparison"],
        "panel_quotient_comparison",
        relation="undetermined",
        equivalent=None,
        proof_verified=False,
        correspondence=None,
        witness=None,
        reason="constructed_search_limit",
        exact_full_graph_and_retained_interactions_compared=False,
    )
    source["pairs"][index] = rerecord(
        pair,
        "support_transition_pair",
        comparison=comparison,
        relation="undetermined",
        equivalent=None,
        proof_verified=False,
        correspondence=None,
        witness=None,
    )
    result = build_distribution(**source)
    assert result["projection_supported_qualified_count"] == 3
    assert result["assignment_count"] == 1 and result["unmapped_qualified_count"] == 2
    assert result["registered_pair_count"] == 3 and result["determinate_pair_count"] == 2
    assert result["W_support"] and not result["complete_quotient_measurement_closed"]
    assert result["complete_class_count"] is result["conditional_distribution"] is None
