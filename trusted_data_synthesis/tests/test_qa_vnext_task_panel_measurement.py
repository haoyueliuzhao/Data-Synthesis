"""Constructed measurement records only: these are NOT additional model samples.

The artificial audit graphs exercise the unchanged finite comparator without
running a finance Operation, a Runtime, a tokenizer, or a Provider.
"""

from __future__ import annotations

import socket

import pytest

from trusted_synthesis.canonical_json import canonical_json_bytes
from trusted_synthesis.domains.finance.qa_vnext.protocol import ProtocolError
from trusted_synthesis.domains.finance.qa_vnext.protocol import record as domain_record
from trusted_synthesis.domains.finance.qa_vnext.runtime import PublicQARuntime
from trusted_synthesis.experiments.finance_qa_vnext_model_execution.models import record
from trusted_synthesis.experiments.finance_qa_vnext_model_execution.transport import HttpxSender
from trusted_synthesis.experiments.finance_qa_vnext_task_panel import measurement


def forbidden(*args, **kwargs):
    pytest.fail("constructed measurement controls may not execute Runtime or Provider calls")


@pytest.fixture(autouse=True)
def no_execution(monkeypatch):
    monkeypatch.setattr(socket.socket, "connect", forbidden)
    monkeypatch.setattr(socket, "create_connection", forbidden)
    monkeypatch.setattr(PublicQARuntime, "run", forbidden)
    monkeypatch.setattr(HttpxSender, "send", forbidden)


def constructed_panel(
    *, outcomes=None, unsupported=(), unit_counts=None, not_fit=(), variants=None
):
    """Build identified, explicitly synthetic records; no saved model artifacts read."""
    outcomes, unit_counts, variants = outcomes or {}, unit_counts or {}, variants or {}
    registrations, qualifications, packages, tokens, coverage = [], [], [], [], []
    for group in measurement.GROUPS:
        task_type, task_id = "constructed_type_" + group, "constructed_task_" + group
        coverage.append(
            record(
                "constructed_coverage",
                task_type=task_type,
                task_id=task_id,
                task_group=group,
                selected_for_model_population=True,
                source_available=True,
                registered_model_sessions=2,
                population_status="selected_model_task",
                control_evidence=True,
            )
        )
        for repeat in (1, 2):
            label = f"{group}{repeat:02d}"
            registration = record(
                "session_registration",
                label=label,
                session_id="constructed_registered_" + label,
                task_group=group,
                task_type=task_type,
                task_id=task_id,
                context_id="constructed_context_" + group,
                protocol_id="constructed_protocol",
                registry_hash="constructed_registry",
                model_configuration_id="constructed_config",
                control_evidence=True,
            )
            registrations.append(registration)
            status = outcomes.get(label, "known_failure")
            success, undecidable = status == "success", status in {"unknown", "not_started"}
            supported = success and label not in unsupported
            session_id = None if undecidable else "constructed_session_" + label
            audit = (
                None
                if undecidable
                else domain_record(
                    "session_audit",
                    context_id=registration["context_id"],
                    task_id=task_id,
                    protocol_id=registration["protocol_id"],
                    registry_hash=registration["registry_hash"],
                    validation_passed=True,
                    qualified=success,
                    trajectory_valid=True,
                    qa_valid=success,
                    errors=[],
                    projection_supported=supported,
                    finite_projection={
                        "nodes": [],
                        "final": {"constructed_result": variants.get(label, 0)},
                    },
                    constructed_session_label=label,
                    control_evidence=True,
                )
            )
            qualification = record(
                "qualification",
                registration_id=registration["id"],
                registered_session_id=registration["session_id"],
                session_id=session_id,
                **{key: registration[key] for key in measurement.PARENT_FIELDS},
                status=status,
                end_to_end_success=None if undecidable else success,
                qualified=None if undecidable else success,
                model_origin_verified=not undecidable,
                evidence_complete=status != "unknown",
                execution_started=status != "not_started",
                projection_status="supported" if supported else "undetermined",
                domain_audit=audit,
                domain_audit_id=audit["id"] if audit else None,
                depth_scope=None
                if undecidable
                else "complete_session"
                if success
                else "reached_prefix",
                depth_metrics=None
                if undecidable
                else {
                    "actual_action_dependency_structural_depth": 2,
                    "actual_action_dependency_semantic_depth": 1,
                    "observable_choice_dependency_depth": 0,
                },
                control_evidence=True,
            )
            qualifications.append(qualification)
            count = unit_counts.get(label, 3) if success else 0
            units = []
            for ordinal in range(count):
                fit = not (label in not_fit and ordinal == count - 1)
                token = record(
                    "constructed_token",
                    row_id=f"constructed_row_{label}_{ordinal}",
                    qualification_id=qualification["id"],
                    session_id=session_id,
                    consumable_token_representation=fit,
                    tokenrepresentation_status="fit" if fit else "not_fit",
                    control_evidence=True,
                )
                tokens.append(token)
                units.append(
                    {"turn_index": ordinal, "consumable": fit, "token_record_id": token["id"]}
                )
            packages.append(
                record(
                    "task_panel_session_package",
                    qualification_id=qualification["id"],
                    label=label,
                    registered_session_id=registration["session_id"],
                    registration_id=registration["id"],
                    session_id=session_id,
                    task_group=group,
                    task_type=task_type,
                    task_id=task_id,
                    qualification_status=status,
                    positive_eligible=success,
                    expected_units=count if success else None,
                    consumable_units=sum(unit["consumable"] for unit in units),
                    units=units,
                    complete=success and bool(units) and all(unit["consumable"] for unit in units),
                    control_evidence=True,
                )
            )
    coverage.extend(
        record(
            "constructed_coverage",
            task_type=f"constructed_unavailable_type_{ordinal}",
            task_id=None,
            task_group=None,
            selected_for_model_population=False,
            source_available=False,
            registered_model_sessions=0,
            population_status="source_uninstantiated",
            control_evidence=True,
        )
        for ordinal in range(3)
    )
    return {
        "qualifications": qualifications,
        "registrations": registrations,
        "coverage": coverage,
        "packages": record("task_panel_session_packages", rows=packages),
        "representation_tokens": record("task_panel_token_dataset", records=tokens),
        "pairs": measurement.finite_comparisons(qualifications),
    }


def task(summary, group):
    return next(item for item in summary["task_rows"] if item["task_group"] == group)


def test_zero_of_two_retains_all_eight_tasks_and_no_conditional_distribution():
    result = measurement.summarize(**constructed_panel())
    assert result["registered_session_denominator"] == 16
    assert result["fixed_task_denominator"] == len(result["task_rows"]) == 8
    assert result["known_failures"] == 16 and result["complete_success_proportion"] == 0
    for row in result["task_rows"]:
        assert row["registered_attempts"] == row["registered_denominator"] == 2
        assert row["complete_success_fraction"] == {"numerator": 0, "denominator": 2}
        assert row["design_task_marginal"] == {"numerator": 1, "denominator": 8}
        assert row["empirical_conditional_class_frequencies"] is None
        assert row["success_pool_task_share"] is None
    assert (
        result["full_support_training_materialization_status"]
        == "support_missing_not_materializable"
    )
    assert not result["missing_training_support_invalidates_collection"]


def test_eleven_type_coverage_preserves_three_uninstantiated_sources_outside_panel_denominators():
    inputs = constructed_panel(outcomes={"F01": "success"})
    result = measurement.summarize(**inputs)
    assert result["registered_task_type_coverage_count"] == len(result["coverage_rows"]) == 11
    assert result["source_available_selected_task_count"] == result["fixed_task_denominator"] == 8
    assert result["source_uninstantiated_task_type_count"] == 3
    assert result["registered_session_denominator"] == 16
    assert result["complete_success_fraction"] == {"numerator": 1, "denominator": 16}
    unavailable = [row for row in result["coverage_rows"] if not row["model_measurement_performed"]]
    assert len(unavailable) == 3
    assert sum(row["registered_attempts"] for row in result["coverage_rows"]) == 16
    for row in unavailable:
        assert row["population_status"] == "source_uninstantiated"
        assert row["registered_attempts"] == row["model_successes"] == 0
        assert row["qualified_mapped"] == row["complete_repr_packages"] == 0
        assert row["complete_success_proportion"] is None
        assert row["task_id"] is row["task_group"] is None
        assert not row["in_fixed_panel_statistical_denominator"]
    inputs["coverage"].pop()
    with pytest.raises(ProtocolError, match="coverage_inventory"):
        measurement.summarize(**inputs)


def test_two_equivalent_successes_keep_point_mass_task_and_exact_sample_denominator():
    inputs = constructed_panel(outcomes={"F01": "success", "F02": "success"})
    assert len(inputs["pairs"]) == 1
    row = task(measurement.summarize(**inputs), "F")
    assert row["complete_success_proportion"] == 1
    assert row["finite_comparison_relation"] == "equivalent"
    assert row["finite_observed_class_count"] == 1
    observed = row["empirical_conditional_class_frequencies"][0]
    assert observed["conditional_frequency"] == {"numerator": 2, "denominator": 2}
    assert len(observed["qualification_ids"]) == 2
    assert row["design_task_marginal"] == {"numerator": 1, "denominator": 8}


def test_one_mapped_success_has_one_finite_observed_class_without_a_pair():
    result = measurement.summarize(**constructed_panel(outcomes={"F01": "success"}))
    row = task(result, "F")
    assert row["model_successes"] == row["known_failures"] == row["qualified_mapped"] == 1
    assert row["complete_success_proportion"] == 0.5
    assert row["empirical_conditional_class_frequencies"][0]["conditional_frequency"] == {
        "numerator": 1,
        "denominator": 1,
    }
    assert row["finite_comparison_status"] == "not_performed_fewer_than_two_qualified"
    assert result["finite_comparison_count"] == 0


def test_two_different_supported_successes_use_unchanged_comparator():
    inputs = constructed_panel(outcomes={"S01": "success", "S02": "success"}, variants={"S02": 1})
    row = task(measurement.summarize(**inputs), "S")
    assert row["finite_comparison_relation"] == "not_equivalent"
    assert row["finite_observed_class_count"] == 2
    assert [
        item["conditional_frequency"] for item in row["empirical_conditional_class_frequencies"]
    ] == [
        {"numerator": 1, "denominator": 2},
        {"numerator": 1, "denominator": 2},
    ]


def test_one_undetermined_projection_does_not_renormalize_other_success():
    inputs = constructed_panel(outcomes={"B01": "success", "B02": "success"}, unsupported=("B02",))
    assert inputs["pairs"] == []
    row = task(measurement.summarize(**inputs), "B")
    assert row["model_successes"] == row["complete_repr_packages"] == 2
    assert row["qualified_mapped"] == row["qualified_projection_undetermined"] == 1
    assert row["complete_success_proportion"] == 1
    assert row["empirical_conditional_class_frequencies"] is None
    assert row["finite_comparison_status"] == "not_performed_unsupported_projection"


@pytest.mark.parametrize("missing", ["unknown", "not_started"])
def test_unknown_and_not_started_keep_denominator_without_becoming_zero(missing):
    result = measurement.summarize(**constructed_panel(outcomes={"F01": "success", "F02": missing}))
    row = task(result, "F")
    assert row["registered_denominator"] == 2 and row[missing] == 1
    assert row["complete_success_proportion"] is None
    assert not row["complete_decidable_population"]
    assert result["complete_success_proportion"] is None
    assert result["complete_success_fraction"] is None
    assert not result["complete_decidable_population"]
    assert not row["success_pool_population_decidable"]
    assert row["model_successes"] == 1 and row["known_failures"] == 0
    assert row["empirical_conditional_class_frequencies"][0]["conditional_frequency"] == {
        "numerator": 1,
        "denominator": 1,
    }


def test_not_fit_is_independent_of_success_qualification_projection_and_task_presence():
    inputs = constructed_panel(
        outcomes={"B01": "success", "B02": "success"},
        unit_counts={"B01": 17, "B02": 17},
        not_fit=("B02",),
    )
    result = measurement.summarize(**inputs)
    row = task(result, "B")
    assert row["model_successes"] == row["qualified_mapped"] == 2
    assert row["complete_repr_packages"] == 1
    assert row["representation_candidate_rows"] == 34
    assert row["representation_fit_rows"] == 33 and row["representation_not_fit_rows"] == 1
    assert row["complete_package_rows"] == 17
    incomplete = next(item for item in result["session_rows"] if item["label"] == "B02")
    assert incomplete["expected_package_units"] == 17
    assert incomplete["consumable_package_units"] == 16
    assert incomplete["qualified"] and not incomplete["complete_representation_package"]
    assert len(result["task_rows"]) == 8 and result["registered_session_denominator"] == 16


def test_pool_task_shares_do_not_replace_uniform_design_marginal():
    result = measurement.summarize(
        **constructed_panel(
            outcomes={"F01": "success", "F02": "success", "B01": "success"},
            unit_counts={"F01": 3, "F02": 3, "B01": 17},
            not_fit=("F02",),
        )
    )
    first, branch = task(result, "F"), task(result, "B")
    assert (
        first["design_task_marginal"]
        == branch["design_task_marginal"]
        == {"numerator": 1, "denominator": 8}
    )
    assert first["success_pool_task_share"] == {"numerator": 2, "denominator": 3}
    assert branch["success_pool_task_share"] == {"numerator": 1, "denominator": 3}
    assert (
        first["complete_package_pool_task_share"]
        == branch["complete_package_pool_task_share"]
        == {
            "numerator": 1,
            "denominator": 2,
        }
    )
    assert first["fit_row_pool_task_share"] == {"numerator": 5, "denominator": 22}
    assert branch["fit_row_pool_task_share"] == {"numerator": 17, "denominator": 22}
    assert branch["complete_package_row_pool_task_share"] == {"numerator": 17, "denominator": 20}
    assert result["final_training_weights"] is None
    assert not result["design_marginal_renormalized"]


def test_full_support_is_separate_witness_not_a_sixteen_success_gate():
    outcomes = {f"{group}01": "success" for group in measurement.GROUPS}
    result = measurement.summarize(**constructed_panel(outcomes=outcomes))
    assert result["complete_success_proportion"] == 0.5
    assert result["complete_repr_packages"] == 8
    assert result["all_selected_tasks_have_success_witness"]
    assert result["full_support_training_support_available"]
    assert not result["full_support_training_materialized"]
    assert (
        result["full_support_training_materialization_status"]
        == "support_available_not_materialized"
    )
    assert result["final_training_weights"] is None
    assert not result["collection_requires_all_sessions_successful"]
    unavailable = measurement.summarize(**constructed_panel(outcomes=outcomes, not_fit=("S01",)))
    assert unavailable["all_selected_tasks_have_success_witness"]
    assert not unavailable["full_support_training_support_available"]
    assert not unavailable["full_support_training_materialized"]
    assert unavailable["full_support_absent_task_groups"] == ["S"]


def test_actual_depth_and_prefix_scope_are_copied_without_task_name_imputation():
    inputs = constructed_panel(outcomes={"B01": "success", "S02": "not_started"})
    before = canonical_json_bytes(inputs)
    result = measurement.summarize(**inputs)
    assert canonical_json_bytes(inputs) == before
    by_label = {item["label"]: item for item in result["session_rows"]}
    assert by_label["B01"]["depth_scope"] == "complete_session"
    assert by_label["B02"]["depth_scope"] == "reached_prefix"
    assert by_label["B01"]["depth_metrics"]["actual_action_dependency_semantic_depth"] == 1
    assert by_label["B02"]["depth_metrics"]["actual_action_dependency_semantic_depth"] == 1
    assert by_label["S02"]["depth_scope"] is by_label["S02"]["depth_metrics"] is None


@pytest.mark.parametrize("relation", ["missing", "undetermined"])
def test_unresolved_pair_does_not_invent_conditional_classes(relation):
    inputs = constructed_panel(outcomes={"F01": "success", "F02": "success"})
    if relation == "missing":
        inputs["pairs"] = []
    else:
        pair = inputs["pairs"][0]
        comparison = pair["comparison"]
        inputs["pairs"] = [
            record(
                "finite_pair",
                task_group="F",
                left_qualification_id=pair["left_qualification_id"],
                right_qualification_id=pair["right_qualification_id"],
                comparison=domain_record(
                    "finite_comparison",
                    left_audit_id=comparison["left_audit_id"],
                    right_audit_id=comparison["right_audit_id"],
                    relation="undetermined",
                    equivalent=None,
                    reason="constructed_undetermined_control",
                ),
            )
        ]
    row = task(measurement.summarize(**inputs), "F")
    assert row["model_successes"] == row["qualified_mapped"] == 2
    assert row["empirical_conditional_class_frequencies"] is None


def test_at_most_eight_same_task_pairs_and_all_sixteen_denominators():
    outcomes = {
        f"{group}{repeat:02d}": "success" for group in measurement.GROUPS for repeat in (1, 2)
    }
    inputs = constructed_panel(outcomes=outcomes)
    assert len(inputs["pairs"]) == 8
    result = measurement.summarize(**inputs)
    assert result["finite_comparison_count"] == 8 and result["success_numerator"] == 16
    assert result["complete_success_fraction"] == {"numerator": 16, "denominator": 16}
    assert result["quotient_assignments"] == []
    assert result["historical_model_sessions_pooled"] == 0
    assert not result["observed_groups_enumerate_all_possible_classes"]


@pytest.mark.parametrize(
    "mutation", ["missing_session", "duplicate_session", "foreign_parent", "missing_package"]
)
def test_registration_inventory_cannot_be_filtered_or_pooled_with_historical_records(mutation):
    inputs = constructed_panel()
    if mutation == "missing_session":
        inputs["qualifications"].pop()
    elif mutation == "duplicate_session":
        inputs["qualifications"][-1] = inputs["qualifications"][0]
    elif mutation == "missing_package":
        inputs["packages"]["rows"].pop()
    else:
        qualification = inputs["qualifications"][0]
        fields = {
            key: value
            for key, value in qualification.items()
            if key not in {"id", "schema_version"}
        }
        fields["registration_id"] = "historical_registration_not_in_new_panel"
        inputs["qualifications"][0] = record("qualification", **fields)
    with pytest.raises(ProtocolError, match="panel_measurement"):
        measurement.summarize(**inputs)


def test_cross_task_pair_rejected_before_conditional_frequency_measurement():
    inputs = constructed_panel(outcomes={"F01": "success", "C01": "success"})
    left, right = [item for item in inputs["qualifications"] if item["qualified"]]
    inputs["pairs"] = [
        record(
            "finite_pair",
            task_group="F",
            left_qualification_id=left["id"],
            right_qualification_id=right["id"],
            comparison={},
        )
    ]
    with pytest.raises(ProtocolError, match="pair_same_task"):
        measurement.summarize(**inputs)
