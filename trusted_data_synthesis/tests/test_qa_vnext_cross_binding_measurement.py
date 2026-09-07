"""New-only constructed population and comparison controls, not model samples.

Each artificial graph carries task-specific evidence IDs and explicit typed
denominators. Only the new pure measurement/comparison code is called. No old
tests, historical artifacts, Runtime, qualification, support producer or token
encoding is executed.
"""

from __future__ import annotations

import copy
import socket

import pytest

from trusted_synthesis.canonical_json import canonical_json_bytes
from trusted_synthesis.domains.finance.qa_vnext.protocol import ProtocolError
from trusted_synthesis.domains.finance.qa_vnext.protocol import record as public_record
from trusted_synthesis.domains.finance.qa_vnext.runtime import PublicQARuntime
from trusted_synthesis.experiments.finance_qa_vnext_cross_binding import measurement, support
from trusted_synthesis.experiments.finance_qa_vnext_model_execution import qualification
from trusted_synthesis.experiments.finance_qa_vnext_model_execution.models import record
from trusted_synthesis.experiments.finance_qa_vnext_model_execution.transport import HttpxSender


def forbidden(*args, **kwargs):
    pytest.fail("constructed measurement controls may not invoke an execution producer")


@pytest.fixture(autouse=True)
def no_producer_calls(monkeypatch):
    monkeypatch.setattr(socket.socket, "connect", forbidden)
    monkeypatch.setattr(socket, "create_connection", forbidden)
    monkeypatch.setattr(PublicQARuntime, "run", forbidden)
    monkeypatch.setattr(HttpxSender, "send", forbidden)
    monkeypatch.setattr(qualification, "qualify_session", forbidden)
    monkeypatch.setattr(support, "actual_support", forbidden)


def rerecord(value, kind, **changes):
    fields = {
        key: copy.deepcopy(item)
        for key, item in value.items()
        if key not in {"id", "schema_version"}
    }
    fields.update(changes)
    return record(kind, **fields)


def graph_for(task, label, reconstructed):
    target, other, relation, total = (
        task["task_id"] + ":" + name for name in ("target", "other", "relation", "total")
    )
    sum_id, ratio_id, percent_id = (label + ":" + name for name in ("sum", "ratio", "percent"))
    denominator = {
        "role": "denominator",
        "kind": "claim" if reconstructed else "evidence",
        "reference": {"producer_action": sum_id} if reconstructed else {"evidence_id": total},
    }
    nodes = [
        {
            "node_id": sum_id,
            "operation": "relation_sum",
            "inputs": [
                {"role": "member", "kind": "evidence", "reference": {"evidence_id": target}},
                {"role": "member", "kind": "evidence", "reference": {"evidence_id": other}},
                {"role": "relation", "kind": "evidence", "reference": {"evidence_id": relation}},
            ],
            "input_dependencies": [],
            "decision_dependencies": [],
        },
        {
            "node_id": ratio_id,
            "operation": "share_ratio",
            "inputs": [
                {"role": "numerator", "kind": "evidence", "reference": {"evidence_id": target}},
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
        "execution_id": label + ":sum_execution",
        "observation_id": label + ":sum_observation",
        "update_submission_id": label + ":sum_update",
    }
    trace = {
        "ratio": {"node_id": ratio_id, "operation": "share_ratio"},
        "actual_denominator": denominator,
        "actual_resolved_denominator": {
            "ref_id": total_trace["accepted_claim_id"] if reconstructed else total,
            "value": {"kind": "claim" if reconstructed else "evidence"},
        },
    }
    if reconstructed:
        trace.update(total=total_trace, accepted_total_claim_actually_consumed_by_ratio=True)
    else:
        trace["disclosed_total_evidence_id"] = total
    final = {
        "answer_producer": {"producer_action": percent_id},
        "result": {"value": "60", "unit": "percent"},
        "citations": [target, other, relation] if reconstructed else [target, total],
    }
    return {"nodes": nodes, "final": final}, trace


def constructed_panel(
    *,
    task_count=3,
    successes=None,
    outcomes=None,
    reconstructed=(),
    unmapped=(),
    variants=None,
    not_fit=(),
    missing_representation=(),
):
    outcomes, variants = outcomes or {}, variants or {}
    tasks = [
        {
            "task_key": f"T{index:02d}",
            "task_group": f"T{index:02d}",
            "task_type": "source_explicit_part_whole_share",
            "task_id": f"constructed_task_{index}",
            "context_id": f"constructed_context_{index}",
            "protocol_id": "constructed_protocol",
            "registry_hash": "constructed_registry",
            "source_binding_id": f"constructed_source_{index}",
        }
        for index in range(1, task_count + 1)
    ]
    labels = [
        f"{task['task_group']}_{profile}{repeat:02d}"
        for repeat in (1, 2)
        for task in tasks
        for profile in ("N", "E")
    ]
    successes = set(labels if successes is None else successes)
    profiles = {
        name: record("constructed_profile", profile=name, control_evidence=True)
        for name in ("N", "E")
    }
    configurations = {
        name: record("constructed_configuration", profile=name, control_evidence=True)
        for name in ("N", "E")
    }
    rule = record("cross_binding_rule", control_evidence=True)
    condition = record(
        "cross_binding_condition",
        tasks=tasks,
        task_count=task_count,
        registered_session_count=4 * task_count,
        sessions_per_task=4,
        sessions_per_task_profile=2,
        registered_labels=labels,
        profiles=profiles,
        configurations=configurations,
        rule_id=rule["id"],
        profile_mixture={name: {"numerator": 1, "denominator": 2} for name in ("N", "E")},
        task_marginal=[
            {
                "task_id": task["task_id"],
                "task_group": task["task_group"],
                "numerator": 1,
                "denominator": task_count,
            }
            for task in tasks
        ],
        control_evidence=True,
    )
    contract = measurement.comparison_contract(condition, rule)
    entries, projections = [], []
    for label in labels:
        task = next(task for task in tasks if label.startswith(task["task_group"] + "_"))
        profile = label.split("_")[1][0]
        status = outcomes.get(label, "success" if label in successes else "known_failure")
        valid, missing = status == "success", status in {"unknown", "not_started"}
        reg = record(
            "session_registration",
            label=label,
            run_condition_id=condition["id"],
            session_id="constructed_registered_" + label,
            **{key: task[key] for key in measurement.TASK_FIELDS},
            profile=profile,
            profile_id=profiles[profile]["id"],
            model_configuration_id=configurations[profile]["id"],
            control_evidence=True,
        )
        base, trace = graph_for(task, label, label in reconstructed)
        session = (
            None
            if missing
            else public_record("session", constructed_label=label, control_evidence=True)
        )
        graph = (
            None
            if missing
            else public_record("actual_decision_graph", nodes=base["nodes"], control_evidence=True)
        )
        audit = (
            None
            if missing
            else public_record(
                "session_audit",
                session_id=session["id"],
                actual_decision_graph=graph,
                finite_projection=base,
                projection_supported=valid and label not in unmapped,
                control_evidence=True,
            )
        )
        qual = record(
            "qualification",
            registration_id=reg["id"],
            registered_session_id=reg["session_id"],
            session_id=session["id"] if session else None,
            domain_audit=audit,
            domain_audit_id=audit["id"] if audit else None,
            **{key: task[key] for key in measurement.TASK_FIELDS},
            model_configuration_id=reg["model_configuration_id"],
            status=status,
            qualified=None if missing else valid,
            end_to_end_success=None if missing else valid,
            evidence_complete=status != "unknown",
            model_origin_verified=not missing,
            depth_scope=None if missing else "complete_session" if valid else "reached_prefix",
            depth_metrics=None if missing else {"constructed_actual_depth": 2},
            control_evidence=True,
        )
        metadata = {
            **{
                key: reg[key]
                for key in (
                    *measurement.TASK_FIELDS,
                    "profile",
                    "profile_id",
                    "model_configuration_id",
                )
            },
            "rule_id": rule["id"],
            "generation_condition_id": condition["id"],
            "comparison_contract_id": contract["id"],
            "registration_id": reg["id"],
            "label": label,
            "session_id": qual["session_id"],
            "qualification_id": qual["id"],
            "qualification_status": status,
            "old_domain_audit_id": qual["domain_audit_id"],
            "source_actual_graph_id": graph["id"] if graph else None,
            "old_projection_supported": bool(audit and audit["projection_supported"]),
        }
        anchor = record(
            "cross_binding_actual_base_anchor",
            **metadata,
            finite_projection=base if audit else None,
        )
        proof = record(
            "cross_binding_support",
            qualification_id=qual["id"],
            registration_id=reg["id"],
            session_id=qual["session_id"],
            base_anchor_id=anchor["id"],
            task_id=task["task_id"],
            context_id=task["context_id"],
            qualified=qual["qualified"],
            qualification_status=status,
            source_actual_graph_id=graph["id"] if graph else None,
            support="reconstructed_total"
            if valid and label in reconstructed
            else "disclosed_total"
            if valid
            else "ineligible",
            proof_verified=valid,
            trace=trace if valid else None,
            control_evidence=True,
        )
        supported = valid and label not in unmapped
        projections.append(
            record(
                "panel_quotient_projection",
                **metadata,
                base_anchor=anchor,
                actual_support=proof,
                supported=supported,
                status="supported" if supported else "undetermined" if valid else "ineligible",
                behavior_projection={
                    **base,
                    "retained_interactions": [{"constructed_variant": variants[label]}]
                    if label in variants
                    else [],
                }
                if supported
                else None,
                interpretation_ledger=[{"constructed_raw_label": label}],
                interpretation_details=[],
                control_evidence=True,
            )
        )
        package = (
            None
            if label in missing_representation
            else record(
                "constructed_session_package",
                registration_id=reg["id"],
                qualification_id=qual["id"],
                session_id=qual["session_id"],
                complete=valid and label not in not_fit,
                control_evidence=True,
            )
        )
        entries.append(
            {
                "label": label,
                "registration": reg,
                "qualification": qual,
                "session": session,
                "package": package,
                "target_token_count": None
                if label in missing_representation
                else 70
                if valid
                else 0,
            }
        )
    return {
        "entries": entries,
        "projections": projections,
        "condition": condition,
        "rule": rule,
        "contract": contract,
    }


def task(result, group):
    return next(row for row in result["task_rows"] if row["task_group"] == group)


def profile(row, name):
    return next(item for item in row["profile_rows"] if item["profile"] == name)


def test_contract_is_pre_response_and_exactly_eighteen_same_task_label_pairs():
    source = constructed_panel()
    contract = source["contract"]
    assert contract["task_count"] == 3 and contract["registered_session_count"] == 12
    assert contract["maximum_pairs_per_task"] == 6 and contract["maximum_same_task_pairs"] == 18
    assert len(contract["registered_same_task_label_pairs"]) == 18
    assert "qualification_ids" not in contract
    assert not contract["cross_task_state_comparison_allowed"]
    assert all(
        row["left_label"].split("_")[0] == row["right_label"].split("_")[0]
        for row in contract["registered_same_task_label_pairs"]
    )


def test_same_mechanism_profiles_give_one_class_per_task_not_one_class_per_profile():
    result = measurement.analyze(**constructed_panel())
    assert result["registered_session_count"] == result["qualified_count"] == 12
    assert result["panel_success_fraction"] == {"numerator": 12, "denominator": 12}
    assert result["pair_count"] == 18 and result["cross_task_state_comparisons"] == 0
    assert len(result["classes"]) == 3 and len(result["assignments"]) == 12
    assert len({ref["task_id"] for ref in result["classes"]}) == 3
    for row in result["task_rows"]:
        assert row["design_task_marginal"] == {"numerator": 1, "denominator": 3}
        assert row["complete_class_count"] == 1 and row["observed_qualified_pairs"] == 6
        assert row["conditional_distribution"][0]["conditional_frequency"] == {
            "numerator": 4,
            "denominator": 4,
        }
        assert not row["W_support"]
    assert result["pooled_cross_task_conditional_distribution"] is None
    assert not result["finite_cross_binding_DR_reuse_witness"]


def test_cross_task_comparison_fails_before_graph_search_even_with_same_operation_shapes(
    monkeypatch,
):
    source = constructed_panel()
    left = next(entry for entry in source["entries"] if entry["label"] == "T01_N01")
    right = next(entry for entry in source["entries"] if entry["label"] == "T02_N01")
    projections = {row["label"]: row for row in source["projections"]}
    monkeypatch.setattr(measurement, "compare_projections", forbidden)
    with pytest.raises(ProtocolError, match="no_cross_task_state_comparison"):
        measurement.compare_within_task(
            left,
            right,
            projections[left["label"]],
            projections[right["label"]],
            source["condition"],
            source["rule"],
            source["contract"],
        )


def test_two_new_bindings_can_each_have_dr_witness_without_cross_task_state_identity():
    result = measurement.analyze(**constructed_panel(reconstructed=("T01_N01", "T02_E01")))
    assert task(result, "T01")["W_support"] and task(result, "T02")["W_support"]
    assert not task(result, "T03")["W_support"]
    assert result["tasks_with_DR_witness"] == 2 and result["finite_cross_binding_DR_reuse_witness"]
    assert len(result["classes"]) == 5
    for pair in result["pairs"]:
        assert pair["left_label"].split("_")[0] == pair["right_label"].split("_")[0]
        if pair["execution_support_contrast"]["established"]:
            contrast = pair["execution_support_contrast"]
            assert {
                contrast["left"]["denominator"]["kind"],
                contrast["right"]["denominator"]["kind"],
            } == {"claim", "evidence"}


def test_task_and_profile_success_denominators_and_success_mixture_are_separate():
    successes = ("T01_N01", "T01_E01", "T01_E02", "T02_N01")
    result = measurement.analyze(
        **constructed_panel(successes=successes, reconstructed=("T01_E01", "T01_E02"))
    )
    first = task(result, "T01")
    assert first["success_fraction"] == {"numerator": 3, "denominator": 4}
    assert profile(first, "N")["success_fraction"] == {"numerator": 1, "denominator": 2}
    assert profile(first, "E")["success_fraction"] == {"numerator": 2, "denominator": 2}
    assert first["success_conditioned_profile_mixture"] == {
        "N": {"numerator": 1, "denominator": 3},
        "E": {"numerator": 2, "denominator": 3},
    }
    assert sorted(
        row["conditional_frequency"]["numerator"] for row in first["conditional_distribution"]
    ) == [1, 2]
    assert all(
        row["conditional_frequency"]["denominator"] == 3
        for row in first["conditional_distribution"]
    )
    assert result["panel_success_fraction"] == {"numerator": 4, "denominator": 12}
    assert task(result, "T03")["success_fraction"] == {"numerator": 0, "denominator": 4}
    assert task(result, "T03")["design_task_marginal"] == {"numerator": 1, "denominator": 3}
    assert len(result["task_rows"]) == 3 and result["pair_count"] == 3


@pytest.mark.parametrize("missing", ["unknown", "not_started"])
def test_missing_outcome_keeps_task_profile_panel_denominators_and_bounds(missing):
    result = measurement.analyze(
        **constructed_panel(successes=("T01_N01", "T02_N01"), outcomes={"T03_E02": missing})
    )
    assert result["registered_session_count"] == 12 and result["panel_success_fraction"] is None
    assert result["panel_success_fraction_bounds"] == {
        "lower": {"numerator": 2, "denominator": 12},
        "upper": {"numerator": 3, "denominator": 12},
    }
    third = task(result, "T03")
    assert third["registered_denominator"] == 4 and third["success_fraction"] is None
    assert third["success_fraction_bounds"]["upper"] == {"numerator": 1, "denominator": 4}
    assert profile(third, "E")["registered_denominator"] == 2
    assert profile(third, "E")["success_fraction_bounds"]["upper"] == {
        "numerator": 1,
        "denominator": 2,
    }
    assert third["conditional_distribution"] is None
    assert task(result, "T01")["conditional_distribution"] is not None
    assert not result["missing_outcomes_counted_as_failures"]


def test_unmapped_valid_mass_keeps_pi_null_but_same_task_dr_witness_survives():
    source = constructed_panel(
        successes=("T01_N01", "T01_N02", "T01_E01", "T01_E02"),
        reconstructed=("T01_N01",),
        unmapped=("T01_N02",),
    )
    result = measurement.analyze(**source)
    first = task(result, "T01")
    assert first["qualified_count"] == 4 and first["assigned_qualified_count"] == 3
    assert first["unmapped_qualified_count"] == 1 and first["conditional_distribution"] is None
    assert first["complete_class_count"] is None and first["W_support"]
    assert first["observed_qualified_pairs"] == 6 and first["determinate_pair_count"] == 3
    assert first["unmapped_valid_joint_mass"] == {"numerator": 1, "denominator": 4}
    assert profile(first, "E")["conditional_distribution"] is not None
    assert profile(first, "N")["conditional_distribution"] is None
    assert result["unmapped_valid_joint_mass"] == {"numerator": 1, "denominator": 12}
    assert result["panel_success_fraction"] == {"numerator": 4, "denominator": 12}


def test_other_retained_behavior_classes_are_not_automatically_two_support_mechanisms():
    result = measurement.analyze(
        **constructed_panel(
            successes=("T01_N01", "T01_E01"), variants={"T01_E01": "different_assertion"}
        )
    )
    first = task(result, "T01")
    assert (
        first["complete_class_count"] == 2
        and first["at_least_two_semantically_distinct_qualified_behaviors"]
    )
    assert (
        not first["W_support"]
        and first["actual_qualified_support_counts"]["reconstructed_total"] == 0
    )


@pytest.mark.parametrize("count", [1, 2])
def test_smaller_panel_requires_its_own_pre_response_exact_condition(count):
    result = measurement.analyze(**constructed_panel(task_count=count, reconstructed=("T01_N01",)))
    assert result["task_count"] == count and result["registered_session_count"] == 4 * count
    assert result["maximum_same_task_pairs"] == result["pair_count"] == 6 * count
    assert all(
        row["design_task_marginal"] == {"numerator": 1, "denominator": count}
        for row in result["task_rows"]
    )
    assert result["multiple_task_bindings_present"] is (count > 1)
    assert not result["finite_cross_binding_DR_reuse_witness"]


def test_zero_success_preserves_all_tasks_and_does_not_require_retry_or_two_classes():
    result = measurement.analyze(**constructed_panel(successes=()))
    assert result["qualified_count"] == result["pair_count"] == len(result["classes"]) == 0
    assert result["known_failure_count"] == result["registered_session_count"] == 12
    assert result["panel_success_fraction"] == {"numerator": 0, "denominator": 12}
    assert len(result["task_rows"]) == 3
    assert all(
        row["bounded_zero_success_result"] and row["conditional_distribution"] is None
        for row in result["task_rows"]
    )
    assert not result["W_support_required_for_workflow_completion"]
    assert result["all_task_joint_frequencies_complete"]
    assert not result["all_task_distributions_complete"]


def test_class_members_preserve_profile_package_tokens_and_correction_references():
    result = measurement.analyze(
        **constructed_panel(not_fit=("T01_E01",), missing_representation=("T02_E01",))
    )
    assert result["qualified_count"] == 12
    first = next(ref for ref in result["classes"] if ref["task_group"] == "T01")
    assert first["profile_counts"] == {"N": 2, "E": 2}
    assert first["complete_package_count"] == 3 and first["target_token_count"] == 280
    member = next(
        row for row in first["member_representation_references"] if row["label"] == "T01_E01"
    )
    assert member["package_id"] and member["package_complete"] is False
    assert member["profile"] == "E" and member["profile_id"] and member["model_configuration_id"]
    assert member["interpretation_ledger"] and member["target_token_count"] == 70
    second = next(ref for ref in result["classes"] if ref["task_group"] == "T02")
    assert second["target_token_count"] is None
    assert not task(result, "T02")["representation_reference_population_complete"]
    assert task(result, "T01")["complete_class_count"] == 1


@pytest.mark.parametrize(
    "mutation", ["drop_task", "duplicate", "old_label", "foreign_generation", "wrong_task_marginal"]
)
def test_current_panel_cannot_import_old_samples_or_shrink_after_outcomes(mutation):
    source = constructed_panel()
    if mutation == "drop_task":
        source["entries"] = [
            entry for entry in source["entries"] if entry["registration"]["task_group"] != "T03"
        ]
        source["projections"] = [row for row in source["projections"] if row["task_group"] != "T03"]
    elif mutation == "duplicate":
        source["entries"][-1] = source["entries"][0]
    elif mutation == "old_label":
        source["entries"][0]["label"] = "N03"
    elif mutation == "foreign_generation":
        entry = source["entries"][0]
        entry["registration"] = rerecord(
            entry["registration"],
            "session_registration",
            run_condition_id="old_single_share_generation",
        )
    else:
        marginal = copy.deepcopy(source["condition"]["task_marginal"])
        marginal[-1]["numerator"] = 0
        source["condition"] = rerecord(
            source["condition"], "cross_binding_condition", task_marginal=marginal
        )
    with pytest.raises(ProtocolError, match="cross_measurement"):
        measurement.analyze(**source)


def test_support_label_cannot_turn_unused_sum_into_actual_reconstructed_denominator():
    source = constructed_panel(successes=("T01_N01", "T01_E01"))
    projection = source["projections"][0]
    forged = rerecord(
        projection["actual_support"], "cross_binding_support", support="reconstructed_total"
    )
    source["projections"][0] = rerecord(
        projection, "panel_quotient_projection", actual_support=forged
    )
    with pytest.raises((ProtocolError, KeyError)):
        measurement.analyze(**source)


def test_support_proof_base_anchor_cannot_refer_to_another_task_or_historical_projection():
    source = constructed_panel()
    projection = source["projections"][0]
    forged = rerecord(
        projection["actual_support"],
        "cross_binding_support",
        base_anchor_id="historical_support_projection",
    )
    source["projections"][0] = rerecord(
        projection, "panel_quotient_projection", actual_support=forged
    )
    with pytest.raises(ProtocolError, match="actual_support_source_binding"):
        measurement.analyze(**source)


def test_analysis_does_not_modify_conditions_profiles_inputs_or_raw_support():
    source = constructed_panel(reconstructed=("T01_N01",), outcomes={"T03_E02": "not_started"})
    before = canonical_json_bytes(source)
    result = measurement.analyze(**source)
    assert canonical_json_bytes(source) == before
    assert result["provider_calls_by_measurement"] == result["runtime_calls_by_measurement"] == 0
    assert result["qualifier_calls_by_measurement"] == result["tokenizer_calls_by_measurement"] == 0
    assert (
        result["historical_model_samples_pooled"] == 0 and result["final_training_weights"] is None
    )
    assert result["pooled_cross_task_conditional_distribution"] is None
