"""Pure constructed-record controls, not new model sessions or task executions.

The artificial one-node graphs exist only to exercise finite assignment and
denominator logic. They are explicitly marked as control evidence; no historical
qualification is rerun and no actual candidate, token or package is rewritten.
"""

from __future__ import annotations

import copy
import socket
from fractions import Fraction

import pytest

from trusted_synthesis.canonical_json import canonical_json_bytes
from trusted_synthesis.domains.finance.qa_vnext import measurement as domain
from trusted_synthesis.domains.finance.qa_vnext.protocol import ProtocolError
from trusted_synthesis.domains.finance.qa_vnext.protocol import record as public_record
from trusted_synthesis.domains.finance.qa_vnext.runtime import PublicQARuntime
from trusted_synthesis.experiments.finance_qa_vnext_model_execution import qualification
from trusted_synthesis.experiments.finance_qa_vnext_model_execution.models import record
from trusted_synthesis.experiments.finance_qa_vnext_model_execution.transport import HttpxSender
from trusted_synthesis.experiments.finance_qa_vnext_panel_quotient.comparison import (
    compare_projections,
)
from trusted_synthesis.experiments.finance_qa_vnext_panel_quotient.distribution import (
    GROUPS,
    TASK_FIELDS,
    build_distribution,
)


def forbidden(*args, **kwargs):
    pytest.fail("constructed distribution controls may not run a producer or old qualification")


@pytest.fixture(autouse=True)
def no_producers(monkeypatch):
    monkeypatch.setattr(socket.socket, "connect", forbidden)
    monkeypatch.setattr(socket, "create_connection", forbidden)
    monkeypatch.setattr(PublicQARuntime, "run", forbidden)
    monkeypatch.setattr(HttpxSender, "send", forbidden)
    monkeypatch.setattr(qualification, "qualify_session", forbidden)
    monkeypatch.setattr(qualification, "compare_qualified_sessions", forbidden)
    monkeypatch.setattr(domain, "audit_session", forbidden)
    monkeypatch.setattr(domain, "compare_sessions", forbidden)


def reidentified(value, kind, **changes):
    fields = {
        key: copy.deepcopy(item)
        for key, item in value.items()
        if key not in {"id", "schema_version"}
    }
    fields.update(changes)
    return record(kind, **fields)


def constructed_panel(*, unsupported=(), variants=None, metadata_error_counts=None):
    """Freeze sixteen constructed controls with exactly S01 ineligible."""
    variants, metadata_error_counts = variants or {}, metadata_error_counts or {}
    generation = record("constructed_generation", control_evidence=True)
    rule = record(
        "panel_quotient_rule", control_evidence=True, purpose="constructed distribution controls"
    )
    entries, projections = [], []
    for group in GROUPS:
        for repeat in (1, 2):
            label = f"{group}{repeat:02d}"
            valid = label != "S01"
            registration = record(
                "session_registration",
                label=label,
                session_id="constructed_registered_" + label,
                run_condition_id=generation["id"],
                task_group=group,
                task_type="constructed_type_" + group,
                task_id="constructed_task_" + group,
                context_id="constructed_context_" + group,
                protocol_id="constructed_protocol",
                registry_hash="constructed_registry",
                control_evidence=True,
            )
            node_id = "constructed_action_" + label
            nodes = [
                {
                    "node_id": node_id,
                    "operation": "lookup",
                    "inputs": [],
                    "parameters": {"constructed_semantic_variant": variants.get(label, 0)},
                    "input_dependencies": [],
                    "decision_dependencies": [],
                }
            ]
            final = {"answer_producer": {"producer_action": node_id}, "result": {"value": "7"}}
            old_projection = {"nodes": nodes, "final": final if valid else None}
            graph = public_record("actual_decision_graph", nodes=nodes, control_evidence=True)
            session = public_record("session", constructed_label=label, control_evidence=True)
            old_supported = valid and label not in {"D01", "B01", "S02"}
            audit = public_record(
                "session_audit",
                session_id=session["id"],
                actual_decision_graph=graph,
                finite_projection=old_projection,
                projection_supported=old_supported,
                control_evidence=True,
            )
            qual = record(
                "qualification",
                registration_id=registration["id"],
                registered_session_id=registration["session_id"],
                session_id=session["id"],
                domain_audit_id=audit["id"],
                domain_audit=audit,
                **{key: registration[key] for key in TASK_FIELDS},
                qualified=valid,
                end_to_end_success=valid,
                status="success" if valid else "known_failure",
                evidence_complete=True,
                model_origin_verified=True,
                control_evidence=True,
            )
            package = record(
                "task_panel_session_package",
                registration_id=registration["id"],
                qualification_id=qual["id"],
                session_id=session["id"],
                complete=valid,
                control_evidence=True,
            )
            entries.append(
                {
                    "label": label,
                    "registration": registration,
                    "qualification": qual,
                    "session": session,
                    "audit": audit,
                    "graph": graph,
                    "old_projection": old_projection,
                    "package": package,
                }
            )
            supported = valid and label not in unsupported
            projections.append(
                record(
                    "panel_quotient_projection",
                    rule_id=rule["id"],
                    generation_condition_id=generation["id"],
                    registration_id=registration["id"],
                    label=label,
                    **{key: registration[key] for key in TASK_FIELDS if key != "task_type"},
                    session_id=session["id"],
                    qualification_id=qual["id"],
                    old_domain_audit_id=audit["id"],
                    source_actual_graph_id=graph["id"],
                    old_projection_supported=old_supported,
                    status="supported" if supported else "undetermined" if valid else "ineligible",
                    supported=supported,
                    behavior_projection={
                        "nodes": nodes,
                        "final": final,
                        "retained_interactions": [],
                    }
                    if supported
                    else None,
                    metadata_error_count=metadata_error_counts.get(label, 0),
                    control_evidence=True,
                )
            )
    condition = record(
        "panel_quotient_condition",
        generation_condition_id=generation["id"],
        rule_id=rule["id"],
        registration_ids=[entry["registration"]["id"] for entry in entries],
        qualification_ids=[entry["qualification"]["id"] for entry in entries],
        qualified_qualification_ids=[
            entry["qualification"]["id"] for entry in entries if entry["qualification"]["qualified"]
        ],
        session_ids=[entry["session"]["id"] for entry in entries],
        original_registration_count=16,
        original_qualified_count=15,
        task_marginal={group: {"numerator": 1, "denominator": 8} for group in GROUPS},
        frozen_outcomes=[
            {
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
        ],
        control_evidence=True,
    )
    comparisons = []
    for group in GROUPS:
        valid = [
            projection
            for projection in projections
            if projection["task_group"] == group and projection["status"] != "ineligible"
        ]
        if len(valid) == 2:
            comparisons.append(compare_projections(*valid))
    return {
        "entries": entries,
        "projections": projections,
        "comparisons": comparisons,
        "condition": condition,
        "rule": rule,
    }


def task(result, group):
    return next(row for row in result["task_distributions"] if row["task_group"] == group)


def rational(value):
    return Fraction(value["numerator"], value["denominator"])


def test_closed_panel_has_fifteen_formal_assignments_and_eight_task_bound_classes():
    source = constructed_panel()
    result = build_distribution(**source)
    assert result["complete_panel_quotient_measurement_closed"]
    assert result["registered_session_count"] == len(result["assignment_status_rows"]) == 16
    assert result["qualified_count"] == result["assignment_count"] == 15
    assert result["unmapped_qualified_count"] == 0
    assert result["pair_count"] == result["determinate_pair_count"] == 7
    assert len(result["classes"]) == result["registered_task_count"] == 8
    assert result["all_observed_task_supports_singleton"]
    assert result["within_task_class_reallocation_degrees_of_freedom"] == 0
    assert result["historical_panel_success_fraction"] == {"numerator": 15, "denominator": 16}
    assert result["historical_panel_success_proportion"] == 0.9375
    class_ids = {ref["id"] for ref in result["classes"]}
    assert len({ref["task_id"] for ref in result["classes"]}) == 8
    for assignment in result["assignments"]:
        assert assignment["class_ref_id"] in class_ids
        assert assignment["measurement_condition_id"] == source["condition"]["id"]
        assert (
            assignment["generation_condition_id"] == source["condition"]["generation_condition_id"]
        )
        assert assignment["rule_id"] == source["rule"]["id"]
        assert assignment["formal_finite_source_bound_assignment"]
        assert assignment["qualification_id"] in source["condition"]["qualified_qualification_ids"]
        assert assignment["comparison_proof_ids"] or assignment["label"] == "S02"


def test_q_joint_u_and_success_conditional_pi_are_not_conflated():
    result = build_distribution(**constructed_panel())
    share = task(result, "S")
    assert share["registered_session_count"] == 2 and share["qualified_count"] == 1
    assert share["historical_success_fraction"] == {"numerator": 1, "denominator": 2}
    assert share["class_joint_frequencies"][0]["joint_frequency_over_registered_sessions"] == {
        "numerator": 1,
        "denominator": 2,
    }
    assert share["conditional_distribution"][0]["conditional_frequency"] == {
        "numerator": 1,
        "denominator": 1,
    }
    for row in result["task_distributions"]:
        assert row["design_task_marginal"] == {"numerator": 1, "denominator": 8}
        assert sum(
            rational(value["joint_frequency_over_registered_sessions"])
            for value in row["class_joint_frequencies"]
        ) == rational(row["historical_success_fraction"])
        assert (
            sum(
                rational(value["conditional_frequency"])
                for value in row["conditional_distribution"]
            )
            == 1
        )
    assert sum(
        rational(row["weighted_joint_frequency"])
        for row in result["panel_weighted_joint_frequencies"]
    ) == Fraction(15, 16)
    assert task(result, "B")["success_pool_task_share"] == {"numerator": 2, "denominator": 15}
    assert share["success_pool_task_share"] == {"numerator": 1, "denominator": 15}
    assert not result["task_marginal_renormalized"]
    assert result["final_training_weights"] is None
    assert not result["full_support_training_materialized"]


def test_failed_s01_has_no_assignment_or_valid_state_mass():
    result = build_distribution(**constructed_panel())
    failed = next(row for row in result["assignment_status_rows"] if row["label"] == "S01")
    assert failed["original_status"] == "known_failure" and failed["original_qualified"] is False
    assert failed["assignment_id"] is failed["class_ref_id"] is None
    assert failed["assignment_status"] == "ineligible_not_qualified"
    assert all(assignment["label"] != "S01" for assignment in result["assignments"])
    assert result["known_failure_count"] == 1
    assert not result["failure_mass_entered_valid_state_distribution"]


def test_different_projection_hashes_group_only_via_checked_correspondence(monkeypatch):
    source = constructed_panel()
    first = source["comparisons"][0]
    assert first["left_projection_id"] != first["right_projection_id"]
    assert first["correspondence"] and first["relation"] == "equivalent"
    monkeypatch.setattr(domain, "_isomorphism", forbidden)
    result = build_distribution(**source)
    assert result["assignment_count"] == 15
    ref = next(item for item in result["classes"] if item["task_group"] == "F")
    assert ref["observed_count"] == 2
    assert ref["relation_basis"] == "checked_equivalence_correspondence"
    assert not ref["content_hash_is_relation_authority"]


def test_real_retained_difference_proof_creates_two_finite_classes_without_value_judgment():
    result = build_distribution(**constructed_panel(variants={"D02": 1}))
    change = task(result, "D")
    assert change["comparison_relation"] == "not_equivalent"
    assert change["observed_class_count"] == 2
    assert [row["conditional_frequency"] for row in change["conditional_distribution"]] == [
        {"numerator": 1, "denominator": 2},
        {"numerator": 1, "denominator": 2},
    ]
    assert (
        len(result["classes"]) == 9
        and result["within_task_class_reallocation_degrees_of_freedom"] == 1
    )
    assert result["complete_panel_quotient_measurement_closed"]
    assert not result["contribution_estimated"] and not result["class_weights_assigned"]


def test_error_count_metadata_does_not_manufacture_strategy_classes():
    result = build_distribution(**constructed_panel(metadata_error_counts={"B01": 99, "D01": 1}))
    assert len(result["classes"]) == 8
    assert all(not ref["error_count_is_class_authority"] for ref in result["classes"])
    assert task(result, "B")["comparison_relation"] == "equivalent"


@pytest.mark.parametrize("label", ["D01", "B01", "S02"])
def test_unmapped_valid_observation_remains_in_m_and_pi_stays_null(label):
    source = constructed_panel(unsupported=(label,))
    result = build_distribution(**source)
    group = task(result, label[0])
    expected_m = 1 if label == "S02" else 2
    assert group["qualified_count"] == expected_m and group["registered_session_count"] == 2
    assert group["unmapped_qualified_count"] == 1
    assert group["assignment_count"] == expected_m - 1
    assert group["conditional_distribution"] is None
    assert group["unmapped_joint_mass"] == {"numerator": 1, "denominator": 2}
    assert rational(group["mapped_joint_mass"]) + rational(
        group["unmapped_joint_mass"]
    ) == rational(group["historical_success_fraction"])
    assert result["qualified_count"] == 15 and result["assignment_count"] == 14
    assert result["historical_panel_success_fraction"] == {"numerator": 15, "denominator": 16}
    assert result["panel_unmapped_joint_mass"] == {"numerator": 1, "denominator": 16}
    assert not result["complete_panel_quotient_measurement_closed"]
    assert result["all_observed_task_supports_singleton"] is None
    assert result["within_task_class_reallocation_degrees_of_freedom"] is None


@pytest.mark.parametrize("kind", ["missing", "undetermined"])
def test_two_supported_observations_need_determinate_pair_before_formal_assignment(kind):
    source = constructed_panel()
    pair = next(item for item in source["comparisons"] if item["task_group"] == "B")
    source["comparisons"] = [item for item in source["comparisons"] if item["task_group"] != "B"]
    if kind == "undetermined":
        source["comparisons"].append(
            reidentified(
                pair,
                "panel_quotient_comparison",
                relation="undetermined",
                equivalent=None,
                correspondence=None,
                witness=None,
                reason="constructed_finite_search_bound",
                proof_verified=False,
                exact_full_graph_and_retained_interactions_compared=False,
            )
        )
    result = build_distribution(**source)
    branch = task(result, "B")
    assert branch["projection_supported_qualified_count"] == 2
    assert branch["assignment_count"] == 0 and branch["unmapped_qualified_count"] == 2
    assert branch["class_joint_frequencies"] == [] and branch["conditional_distribution"] is None
    assert branch["conditional_distribution_status"] == f"supported_pair_comparison_{kind}"
    assert result["assignment_count"] == 13 and result["qualified_count"] == 15


@pytest.mark.parametrize(
    "mutation",
    [
        "entry",
        "projection",
        "duplicate",
        "condition_ids",
        "condition_denominator",
        "condition_marginal",
    ],
)
def test_missing_valid_observation_or_shrunken_denominator_is_rejected(mutation):
    source = constructed_panel()
    if mutation == "entry":
        source["entries"] = [entry for entry in source["entries"] if entry["label"] != "D01"]
    elif mutation == "projection":
        source["projections"] = [item for item in source["projections"] if item["label"] != "D01"]
    elif mutation == "duplicate":
        source["entries"][-1] = source["entries"][0]
    elif mutation == "condition_ids":
        source["condition"] = reidentified(
            source["condition"],
            "panel_quotient_condition",
            registration_ids=source["condition"]["registration_ids"][:-1],
        )
    elif mutation == "condition_denominator":
        source["condition"] = reidentified(
            source["condition"], "panel_quotient_condition", original_registration_count=15
        )
    else:
        marginal = copy.deepcopy(source["condition"]["task_marginal"])
        marginal["S"] = {"numerator": 0, "denominator": 7}
        source["condition"] = reidentified(
            source["condition"], "panel_quotient_condition", task_marginal=marginal
        )
    with pytest.raises(ProtocolError, match="panel_quotient_distribution"):
        build_distribution(**source)


def test_s01_promotion_to_supported_projection_is_rejected():
    source = constructed_panel()
    failure = next(item for item in source["projections"] if item["label"] == "S01")
    success = next(item for item in source["projections"] if item["label"] == "S02")
    promoted = reidentified(
        failure,
        "panel_quotient_projection",
        status="supported",
        supported=True,
        behavior_projection=success["behavior_projection"],
    )
    source["projections"] = [
        promoted if item["id"] == failure["id"] else item for item in source["projections"]
    ]
    with pytest.raises(ProtocolError, match="failed_session_has_no_valid_projection"):
        build_distribution(**source)


def test_frozen_qualification_and_outcome_identity_cannot_be_promoted():
    source = constructed_panel()
    failed = next(entry for entry in source["entries"] if entry["label"] == "S01")
    failed["qualification"] = reidentified(
        failed["qualification"],
        "qualification",
        qualified=True,
        end_to_end_success=True,
        status="success",
    )
    with pytest.raises(ProtocolError, match="missing_or_foreign_frozen_entry"):
        build_distribution(**source)
    source = constructed_panel()
    outcomes = copy.deepcopy(source["condition"]["frozen_outcomes"])
    next(row for row in outcomes if row["label"] == "S01")["qualified"] = True
    source["condition"] = reidentified(
        source["condition"], "panel_quotient_condition", frozen_outcomes=outcomes
    )
    with pytest.raises(ProtocolError, match="frozen_outcome_inventory"):
        build_distribution(**source)


@pytest.mark.parametrize(
    "mutation", ["unverified", "bijection", "graph_mismatch", "foreign_rule", "duplicate_pair"]
)
def test_formal_assignment_rejects_invalid_or_unbound_relation_proof(mutation):
    source = constructed_panel()
    pair = source["comparisons"][0]
    if mutation == "unverified":
        replacement = reidentified(pair, "panel_quotient_comparison", proof_verified=False)
    elif mutation == "bijection":
        replacement = reidentified(
            pair, "panel_quotient_comparison", correspondence={"fake": "fake"}
        )
    elif mutation == "foreign_rule":
        replacement = reidentified(pair, "panel_quotient_comparison", rule_id="other_rule")
    elif mutation == "duplicate_pair":
        source["comparisons"][-1] = pair
        replacement = pair
    else:
        right = next(
            item for item in source["projections"] if item["id"] == pair["right_projection_id"]
        )
        graph = copy.deepcopy(right["behavior_projection"])
        graph["retained_interactions"] = [{"constructed_retained_difference": True}]
        changed = reidentified(right, "panel_quotient_projection", behavior_projection=graph)
        source["projections"] = [
            changed if item["id"] == right["id"] else item for item in source["projections"]
        ]
        replacement = reidentified(
            pair, "panel_quotient_comparison", right_projection_id=changed["id"]
        )
    source["comparisons"][0] = replacement
    with pytest.raises(ProtocolError, match="panel_quotient_distribution"):
        build_distribution(**source)


def test_input_order_does_not_change_assignments_and_inputs_are_not_modified():
    source = constructed_panel()
    before = canonical_json_bytes(source)
    expected = build_distribution(**source)
    assert canonical_json_bytes(source) == before
    source["entries"].reverse()
    source["projections"].reverse()
    source["comparisons"].reverse()
    assert build_distribution(**source) == expected
    assert not expected["historical_qualification_changed"]
    assert not expected["original_projection_support_changed"]
    assert not expected["original_representation_modified"]
    assert (
        expected["provider_calls"]
        == expected["runtime_executions"]
        == expected["qualification_calls"]
        == 0
    )
    assert expected["tokenizer_loads"] == expected["tokenizations"] == expected["gpu_jobs"] == 0
