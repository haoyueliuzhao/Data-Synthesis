"""Constructed stratified-measurement controls, not new model observations.

These deliberately artificial qualification and proof records isolate arithmetic
and source binding. They neither replay prior sessions nor test/execute the
Runtime, qualifier, tokenizer, or semantic projection producer.
"""

from __future__ import annotations

import copy
import socket
from itertools import combinations

import pytest

from trusted_synthesis.canonical_json import canonical_json_bytes
from trusted_synthesis.domains.finance.qa_vnext.protocol import ProtocolError
from trusted_synthesis.domains.finance.qa_vnext.runtime import PublicQARuntime
from trusted_synthesis.experiments.finance_qa_vnext_model_execution import qualification
from trusted_synthesis.experiments.finance_qa_vnext_model_execution.models import record
from trusted_synthesis.experiments.finance_qa_vnext_model_execution.transport import HttpxSender
from trusted_synthesis.experiments.finance_qa_vnext_support_exploration.measurement import (
    PROFILES,
    TASK_FIELDS,
    summarize,
)


def forbidden(*args, **kwargs):
    pytest.fail("measurement controls may not invoke a Provider, Runtime, or qualifier")


@pytest.fixture(autouse=True)
def no_producer_calls(monkeypatch):
    monkeypatch.setattr(socket.socket, "connect", forbidden)
    monkeypatch.setattr(socket, "create_connection", forbidden)
    monkeypatch.setattr(HttpxSender, "send", forbidden)
    monkeypatch.setattr(PublicQARuntime, "run", forbidden)
    monkeypatch.setattr(qualification, "qualify_session", forbidden)
    monkeypatch.setattr(qualification, "compare_qualified_sessions", forbidden)


def rerecord(value, kind, **changes):
    fields = {
        key: copy.deepcopy(item)
        for key, item in value.items()
        if key not in {"id", "schema_version"}
    }
    fields.update(changes)
    return record(kind, **fields)


def constructed_source(
    *, successes=(), outcomes=None, support=None, unmapped=(), semantic_classes=None
):
    """Create one explicitly synthetic 4N+4E population with bounded proof fixtures."""
    outcomes, support, semantic_classes = outcomes or {}, support or {}, semantic_classes or {}
    labels = [f"{profile}{index:02d}" for index in range(1, 5) for profile in PROFILES]
    rule = record("constructed_rule", control_evidence=True)
    profiles = {
        profile: record("constructed_profile", profile=profile, control_evidence=True)
        for profile in PROFILES
    }
    configurations = {
        profile: record("constructed_configuration", profile=profile, control_evidence=True)
        for profile in PROFILES
    }
    condition = record(
        "support_exploration_condition",
        registered_session_count=8,
        sessions_per_profile=4,
        registered_labels=labels,
        profiles=profiles,
        configurations=configurations,
        profile_mixture={profile: {"numerator": 1, "denominator": 2} for profile in PROFILES},
        task_group="S",
        task_type="source_explicit_part_whole_share",
        task_id="constructed_share_task",
        context_id="constructed_context",
        protocol_id="constructed_protocol",
        registry_hash="constructed_registry",
        rule_id=rule["id"],
        control_evidence=True,
    )
    contract = record(
        "constructed_comparison_contract",
        exploration_condition_id=condition["id"],
        rule_id=rule["id"],
        control_evidence=True,
    )
    registrations, entries, projections, support_rows = [], [], [], []
    class_key = {}
    for label in labels:
        profile = label[0]
        status = outcomes.get(label, "success" if label in successes else "known_failure")
        missing = status in {"unknown", "not_started"}
        valid = status == "success"
        reg = record(
            "session_registration",
            label=label,
            profile=profile,
            profile_id=profiles[profile]["id"],
            model_configuration_id=configurations[profile]["id"],
            run_condition_id=condition["id"],
            session_id="qa_vnext_support_exploration_session:constructed_" + label,
            **{key: condition[key] for key in TASK_FIELDS},
            control_evidence=True,
        )
        session = (
            None if missing else record("constructed_session", label=label, control_evidence=True)
        )
        qual = record(
            "qualification",
            registration_id=reg["id"],
            registered_session_id=reg["session_id"],
            session_id=session["id"] if session else None,
            model_configuration_id=reg["model_configuration_id"],
            **{key: condition[key] for key in TASK_FIELDS},
            qualified=None if missing else valid,
            end_to_end_success=None if missing else valid,
            status=status,
            evidence_complete=status != "unknown",
            model_origin_verified=not missing,
            depth_scope=None if missing else "complete_session" if valid else "reached_prefix",
            depth_metrics=None if missing else {"constructed_depth": 1},
            provider_attempt_count=None
            if status == "unknown"
            else 0
            if status == "not_started"
            else 3,
            control_evidence=True,
        )
        exported = record(
            "constructed_export",
            candidate_count=int(valid),
            rows=[{"constructed_original_row": label}] if valid else [],
            control_evidence=True,
        )
        registrations.append(reg)
        entries.append(
            {
                "label": label,
                "registration": reg,
                "qualification": qual,
                "session": session,
                "export": exported,
            }
        )
        mapped = valid and label not in unmapped
        projection = record(
            "panel_quotient_projection",
            label=label,
            registration_id=reg["id"],
            qualification_id=qual["id"],
            session_id=qual["session_id"],
            generation_condition_id=condition["id"],
            rule_id=rule["id"],
            profile=profile,
            profile_id=reg["profile_id"],
            model_configuration_id=reg["model_configuration_id"],
            **{key: condition[key] for key in TASK_FIELDS if key != "task_type"},
            supported=mapped,
            status="supported" if mapped else "undetermined" if valid else "ineligible",
            control_evidence=True,
        )
        projections.append(projection)
        actual = support.get(label, "disclosed_total") if valid else "ineligible"
        support_rows.append(
            record(
                "support_exploration_support",
                label=label,
                qualification_id=qual["id"],
                registration_id=reg["id"],
                session_id=qual["session_id"],
                projection_id=projection["id"],
                qualified=qual["qualified"],
                qualification_status=status,
                profile=profile,
                profile_id=reg["profile_id"],
                model_configuration_id=reg["model_configuration_id"],
                support=actual,
                proof_verified=valid and actual != "other_or_undetermined",
                trace={"constructed_actual_support_proof": actual} if valid else {},
                control_evidence=True,
            )
        )
        if mapped:
            class_key[qual["id"]] = semantic_classes.get(label, actual)
    classes, assignments = [], []
    for key in sorted(set(class_key.values())):
        members = [
            projection
            for projection in projections
            if class_key.get(projection["qualification_id"]) == key
        ]
        ref = record(
            "support_exploration_class",
            exploration_condition_id=condition["id"],
            comparison_contract_id=contract["id"],
            rule_id=rule["id"],
            **{field: condition[field] for field in TASK_FIELDS},
            member_qualification_ids=[item["qualification_id"] for item in members],
            member_projection_ids=[item["id"] for item in members],
            control_evidence=True,
        )
        classes.append(ref)
        assignments.extend(
            record(
                "support_exploration_assignment",
                qualification_id=item["qualification_id"],
                projection_id=item["id"],
                class_ref_id=ref["id"],
                exploration_condition_id=condition["id"],
                comparison_contract_id=contract["id"],
                control_evidence=True,
            )
            for item in members
        )
    pairs = []
    for left, right in combinations([item for item in projections if item["supported"]], 2):
        equal = class_key[left["qualification_id"]] == class_key[right["qualification_id"]]
        comparison = record(
            "panel_quotient_comparison",
            left_projection_id=left["id"],
            right_projection_id=right["id"],
            generation_condition_id=condition["id"],
            rule_id=rule["id"],
            **{key: condition[key] for key in TASK_FIELDS if key != "task_type"},
            relation="equivalent" if equal else "not_equivalent",
            equivalent=equal,
            proof_verified=True,
            witness=None
            if equal
            else {"kind": "constructed_retained_support_or_interaction_difference"},
            correspondence={"constructed_right": "constructed_left"} if equal else None,
            control_evidence=True,
        )
        pairs.append(
            record(
                "support_exploration_pair",
                exploration_condition_id=condition["id"],
                comparison_contract_id=contract["id"],
                rule_id=rule["id"],
                left_qualification_id=left["qualification_id"],
                right_qualification_id=right["qualification_id"],
                **{
                    key: comparison[key]
                    for key in (
                        "left_projection_id",
                        "right_projection_id",
                        "relation",
                        "equivalent",
                        "proof_verified",
                        "witness",
                        "correspondence",
                    )
                },
                comparison=comparison,
                control_evidence=True,
            )
        )
    support_by_qid = {row["qualification_id"]: row["support"] for row in support_rows}
    witnesses = [
        pair["id"]
        for pair in pairs
        if pair["relation"] == "not_equivalent"
        and {
            support_by_qid[pair["left_qualification_id"]],
            support_by_qid[pair["right_qualification_id"]],
        }
        == {"disclosed_total", "reconstructed_total"}
    ]
    target = record(
        "support_exploration_target_witness",
        established=bool(witnesses),
        proof_pairs=witnesses,
        exploration_condition_id=condition["id"],
        comparison_contract_id=contract["id"],
        rule_id=rule["id"],
        control_evidence=True,
    )
    valid_ids = {
        entry["qualification"]["id"]
        for entry in entries
        if entry["qualification"]["qualified"] is True
    }
    assigned_ids = {item["qualification_id"] for item in assignments}
    quotient = record(
        "support_exploration_quotient",
        exploration_condition_id=condition["id"],
        comparison_contract_id=contract["id"],
        qualification_ids=[entry["qualification"]["id"] for entry in entries],
        projections=projections,
        support_rows=support_rows,
        assignments=assignments,
        classes=classes,
        pairs=pairs,
        all_valid_mapped=valid_ids == assigned_ids,
        unmapped_qualification_ids=sorted(valid_ids - assigned_ids),
        target_witness=target,
        control_evidence=True,
    )
    return {
        "registrations": registrations,
        "entries": entries,
        "quotient": quotient,
        "condition": condition,
    }


def profile(result, name):
    return next(row for row in result["profile_rows"] if row["profile"] == name)


def test_same_actual_behavior_across_two_prompt_profiles_is_one_class():
    labels = [f"{name}{index:02d}" for name in PROFILES for index in range(1, 5)]
    result = summarize(**constructed_source(successes=labels))
    assert result["registered_denominator"] == result["qualified_count"] == 8
    assert result["observed_assigned_class_count"] == 1
    assert result["observed_qualified_pairs"] == 28
    assert result["conditional_distribution"][0]["conditional_frequency"] == {
        "numerator": 8,
        "denominator": 8,
    }
    assert not result["target_support_witness_established"]
    assert not result["profile_labels_define_classes"]
    assert profile(result, "E")["success_fraction"] == {"numerator": 4, "denominator": 4}
    assert profile(result, "E")["actual_qualified_support_counts"]["disclosed_total"] == 4


def test_success_conditioned_mixture_uses_one_versus_three_not_fixed_halves():
    source = constructed_source(
        successes=("N01", "E01", "E02", "E03"),
        support={label: "reconstructed_total" for label in ("E01", "E02", "E03")},
    )
    result = summarize(**source)
    assert profile(result, "N")["success_fraction"] == {"numerator": 1, "denominator": 4}
    assert profile(result, "E")["success_fraction"] == {"numerator": 3, "denominator": 4}
    assert result["success_fraction"] == {"numerator": 4, "denominator": 8}
    assert result["declared_profile_mixture"] == {
        name: {"numerator": 1, "denominator": 2} for name in PROFILES
    }
    assert result["success_conditioned_profile_mixture"] == {
        "N": {"numerator": 1, "denominator": 4},
        "E": {"numerator": 3, "denominator": 4},
    }
    assert sorted(
        row["conditional_frequency"]["numerator"] for row in result["conditional_distribution"]
    ) == [1, 3]
    assert all(
        row["conditional_frequency"]["denominator"] == 4
        for row in result["conditional_distribution"]
    )
    assert sorted(
        row["observed_joint_frequency"]["numerator"] for row in result["class_joint_frequencies"]
    ) == [1, 3]
    assert all(
        row["observed_joint_frequency"]["denominator"] == 8
        for row in result["class_joint_frequencies"]
    )
    assert result["target_support_witness_established"]


@pytest.mark.parametrize("missing", ["unknown", "not_started"])
def test_missing_outcome_keeps_eight_and_four_denominators_and_null_full_pi(missing):
    source = constructed_source(successes=("N01", "E01"), outcomes={"E04": missing})
    result = summarize(**source)
    assert (
        result["registered_denominator"] == 8
        and profile(result, "E")["registered_denominator"] == 4
    )
    assert result["success_fraction"] is result["success_proportion"] is None
    assert result["success_fraction_bounds"] == {
        "lower": {"numerator": 2, "denominator": 8},
        "upper": {"numerator": 3, "denominator": 8},
    }
    assert profile(result, "E")["success_fraction_bounds"] == {
        "lower": {"numerator": 1, "denominator": 4},
        "upper": {"numerator": 2, "denominator": 4},
    }
    assert not result["outcome_population_complete"]
    assert (
        result["conditional_distribution"]
        is profile(result, "E")["conditional_distribution"]
        is None
    )
    assert profile(result, "N")["conditional_distribution"] is not None
    assert result["observed_qualified_only_conditional_distribution"] is not None
    assert result["success_conditioned_profile_mixture"] is None
    assert result["observed_success_profile_mixture"] == {
        name: {"numerator": 1, "denominator": 2} for name in PROFILES
    }
    assert result["known_failure_count"] == 5 and result[missing] == 1
    assert not result["missing_outcomes_counted_as_failures"]


def test_partial_unmapped_valid_mass_keeps_full_pi_null_without_erasing_proven_support():
    result = summarize(
        **constructed_source(
            successes=("N01", "E01", "E02"),
            support={"E01": "reconstructed_total"},
            unmapped=("E02",),
        )
    )
    assert result["qualified_count"] == 3 and result["assigned_qualified_count"] == 2
    assert result["unmapped_qualified_count"] == 1
    assert result["success_fraction"] == {"numerator": 3, "denominator": 8}
    assert result["mapped_valid_joint_mass"] == {"numerator": 2, "denominator": 8}
    assert result["unmapped_valid_joint_mass"] == {"numerator": 1, "denominator": 8}
    assert result["unmapped_mass_within_observed_qualified"] == {"numerator": 1, "denominator": 3}
    assert (
        result["conditional_distribution"]
        is result["observed_qualified_only_conditional_distribution"]
        is None
    )
    assert profile(result, "E")["conditional_distribution"] is None
    assert profile(result, "N")["conditional_distribution"] is not None
    assert result["target_support_witness_established"]
    assert len(result["target_support_witnesses"]) == 1
    assert not result["support_witness_requires_all_outcomes_or_projections_resolved"]


def test_unknown_elsewhere_does_not_erase_concrete_support_existence():
    result = summarize(
        **constructed_source(
            successes=("N01", "E01"),
            support={"E01": "reconstructed_total"},
            outcomes={"N04": "unknown"},
        )
    )
    assert result["conditional_distribution"] is None and result["success_fraction"] is None
    assert result["target_support_witness_established"]
    assert profile(result, "E")["conditional_distribution"] is not None


def test_two_different_classes_with_same_support_do_not_prove_target_mechanisms():
    result = summarize(
        **constructed_source(
            successes=("N01", "E01"), semantic_classes={"N01": "retained_a", "E01": "retained_b"}
        )
    )
    assert result["observed_assigned_class_count"] == 2
    assert result["at_least_two_semantically_distinct_qualified_behaviors"]
    assert not result["target_support_witness_established"]
    assert not result["reconstructed_support_reached"]


def test_target_support_can_be_witnessed_within_one_profile_and_not_from_names():
    result = summarize(
        **constructed_source(successes=("E01", "E02"), support={"E02": "reconstructed_total"})
    )
    assert profile(result, "N")["success_fraction"] == {"numerator": 0, "denominator": 4}
    assert result["target_support_witness_established"]
    reconstructed_only = summarize(
        **constructed_source(successes=("E01",), support={"E01": "reconstructed_total"})
    )
    assert reconstructed_only["reconstructed_support_reached"]
    assert not reconstructed_only["disclosed_support_reached"]
    assert not reconstructed_only["target_support_witness_established"]


def test_complete_zero_success_is_a_bounded_negative_result_not_a_sampling_gate():
    result = summarize(**constructed_source())
    assert result["success_fraction"] == {"numerator": 0, "denominator": 8}
    assert result["success_fraction_bounds"]["lower"] == result["success_fraction_bounds"]["upper"]
    assert result["known_failure_count"] == 8 and result["bounded_zero_success_result"]
    assert (
        result["conditional_distribution"] is result["success_conditioned_profile_mixture"] is None
    )
    assert result["conditional_distribution_status"] == "no_qualified_observations"
    assert result["class_joint_frequencies"] == [] and result["joint_class_frequencies_complete"]
    assert not result["target_support_witness_established"]
    assert result["scientific_success_count_required_for_workflow_completion"] == 0
    assert not result["scientific_support_witness_required_for_workflow_completion"]


def test_all_unstarted_is_not_zero_success_evidence():
    outcomes = {f"{name}{index:02d}": "not_started" for name in PROFILES for index in range(1, 5)}
    result = summarize(**constructed_source(outcomes=outcomes))
    assert result["success_fraction"] is None and result["known_failure_count"] == 0
    assert result["success_fraction_bounds"] == {
        "lower": {"numerator": 0, "denominator": 8},
        "upper": {"numerator": 8, "denominator": 8},
    }
    assert result["not_started"] == 8 and not result["bounded_zero_success_result"]
    assert result["conditional_distribution_status"] == "outcome_population_incomplete"


@pytest.mark.parametrize(
    "mutation",
    ["missing", "duplicate", "old_s_label", "old_generation", "profile_config", "half_mixture"],
)
def test_old_population_or_shrunken_new_inventory_cannot_enter_measurement(mutation):
    source = constructed_source()
    if mutation == "missing":
        source["entries"].pop()
    elif mutation == "duplicate":
        source["entries"][-1] = source["entries"][0]
    elif mutation == "old_s_label":
        source["registrations"][0] = rerecord(
            source["registrations"][0], "session_registration", label="S02"
        )
    elif mutation in {"old_generation", "profile_config"}:
        changes = (
            {"run_condition_id": "historical_s_condition"}
            if mutation == "old_generation"
            else {"model_configuration_id": "other_profile_config"}
        )
        changed = rerecord(source["registrations"][0], "session_registration", **changes)
        source["registrations"][0] = changed
        source["entries"][0]["registration"] = changed
    else:
        source["condition"] = rerecord(
            source["condition"],
            "support_exploration_condition",
            profile_mixture={
                "N": {"numerator": 1, "denominator": 4},
                "E": {"numerator": 3, "denominator": 4},
            },
        )
    with pytest.raises(ProtocolError, match="exploration_measurement"):
        summarize(**source)


def test_claimed_witness_without_actual_support_proof_is_rejected():
    source = constructed_source(successes=("N01", "E01"), support={"E01": "reconstructed_total"})
    rows = source["quotient"]["support_rows"]
    changed = [
        rerecord(row, "support_exploration_support", proof_verified=False)
        if row["support"] == "reconstructed_total"
        else row
        for row in rows
    ]
    source["quotient"] = rerecord(
        source["quotient"], "support_exploration_quotient", support_rows=changed
    )
    with pytest.raises(ProtocolError, match="actual_support_proof_required"):
        summarize(**source)


def test_two_profile_successes_cannot_be_promoted_to_target_witness():
    source = constructed_source(successes=("N01", "E01"))
    target = rerecord(
        source["quotient"]["target_witness"], "support_exploration_target_witness", established=True
    )
    source["quotient"] = rerecord(
        source["quotient"], "support_exploration_quotient", target_witness=target
    )
    with pytest.raises(ProtocolError, match="target_witness_not_profile_or_class_count"):
        summarize(**source)


def test_missing_qualified_projection_cannot_be_dropped_before_normalizing():
    source = constructed_source(successes=("N01", "E01"))
    remaining = [item for item in source["quotient"]["projections"] if item["label"] != "E01"]
    source["quotient"] = rerecord(
        source["quotient"], "support_exploration_quotient", projections=remaining
    )
    with pytest.raises(ProtocolError, match="projection_support_inventory"):
        summarize(**source)


def test_wrong_common_comparison_condition_is_rejected_not_relaxed_for_profiles():
    source = constructed_source(successes=("N01", "E01"))
    pair = source["quotient"]["pairs"][0]
    comparison = rerecord(
        pair["comparison"],
        "panel_quotient_comparison",
        generation_condition_id="old_neutral_condition",
    )
    altered = rerecord(pair, "support_exploration_pair", comparison=comparison)
    source["quotient"] = rerecord(
        source["quotient"], "support_exploration_quotient", pairs=[altered]
    )
    with pytest.raises(ProtocolError, match="cross_profile_comparison_contract"):
        summarize(**source)


def test_raw_inputs_and_actual_depth_are_not_modified_or_imputed():
    source = constructed_source(successes=("E01",), outcomes={"N01": "unknown"})
    before = canonical_json_bytes(source)
    result = summarize(**source)
    assert canonical_json_bytes(source) == before
    rows = {row["label"]: row for row in result["session_rows"]}
    assert rows["N01"]["depth_scope"] is rows["N01"]["depth_metrics"] is None
    assert rows["E01"]["depth_scope"] == "complete_session"
    assert rows["E01"]["actual_support"] == "disclosed_total"
    assert (
        result["provider_calls_by_measurement"] == result["runtime_executions_by_measurement"] == 0
    )
    assert result["qualifier_calls_by_measurement"] == result["tokenizer_calls_by_measurement"] == 0
    assert (
        result["historical_model_sessions_pooled"] == 0 and result["final_training_weights"] is None
    )
