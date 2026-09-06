"""Small guarded checks for the four formal isolated-control families."""

from __future__ import annotations

import copy
from pathlib import Path

import pytest

from trusted_synthesis.experiments.finance_qa_vnext_model_execution.models import record
from trusted_synthesis.experiments.finance_qa_vnext_panel_quotient.controls import run_controls
from trusted_synthesis.experiments.finance_qa_vnext_panel_quotient.distribution import (
    build_distribution,
)
from trusted_synthesis.experiments.finance_qa_vnext_panel_quotient.guards import (
    guard_report,
    measurement_guard,
)
from trusted_synthesis.experiments.finance_qa_vnext_panel_quotient.projection import project_entry
from trusted_synthesis.experiments.finance_qa_vnext_panel_quotient.rules import quotient_rule
from trusted_synthesis.experiments.finance_qa_vnext_panel_quotient.source import load_inputs
from trusted_synthesis.experiments.finance_qa_vnext_panel_quotient.stage import (
    _comparisons,
    freeze_condition,
)

ROOT = Path(__file__).resolve().parents[2]


@pytest.fixture(scope="module")
def population():
    with measurement_guard() as counts:
        inputs = load_inputs(ROOT)
        rule = quotient_rule()
        inputs["measurement_condition"] = freeze_condition(
            inputs, rule, record("implementation", test_only=True)
        )
        projections = [
            project_entry(entry, rule, inputs["condition"]["id"]) for entry in inputs["entries"]
        ]
        comparisons = _comparisons(inputs, projections)
    assert guard_report(counts, "isolated_control_input")["all_zero"] is True
    return inputs, rule, projections, comparisons


@pytest.fixture(scope="module")
def controlled(population):
    with measurement_guard() as counts:
        result = run_controls(*population)
    assert guard_report(counts, "isolated_control_tests")["all_zero"] is True
    return result


def test_four_families_all_expected_and_no_input_mutation(controlled):
    assert controlled["control_count"] == 24
    assert controlled["executed_control_count"] == 24
    assert controlled["not_applicable_control_count"] == 0
    assert controlled["family_counts"] == {
        "clean_rule_compatibility": 2,
        "no_effect_and_support_boundary": 15,
        "retained_actual_behavior": 2,
        "frozen_population_and_failure_mass": 5,
    }
    assert controlled["all_expected_outcomes"] is True
    assert controlled["original_inputs_and_sidecars_unmodified"] is True
    assert all(row["control_evidence"] and row["passed"] for row in controlled["rows"])
    assert controlled["provider_calls"] == controlled["historical_input_loads"] == 0
    assert controlled["qualification_calls"] == controlled["tokenizations"] == 0
    assert (
        controlled["counterfactual_valid_assignments_written"]
        == controlled["additional_model_samples"]
        == 0
    )


def test_share_counterfactuals_have_difference_witness_without_assignments(controlled):
    rows = [row for row in controlled["rows"] if row["family"] == "retained_actual_behavior"]
    assert len(rows) == 2
    for row in rows:
        assert row["observed"]["final_bytes_unchanged"] is True
        assert row["observed"]["comparison"]["relation"] == "not_equivalent"
        assert row["observed"]["comparison"]["witness"]
        assert row["formal_valid_assignment_created"] is False


def test_undetermined_valid_mass_is_not_renormalized(controlled):
    observed = next(
        row["observed"]
        for row in controlled["rows"]
        if row["name"] == "undetermined_D01_retains_valid_mass_and_null_conditional_pi"
    )
    assert observed["registered_session_count"] == 16 and observed["qualified_count"] == 15
    assert observed["D_qualified_count"] == 2 and observed["D_unmapped_qualified_count"] == 1
    assert observed["D_conditional_distribution"] is None
    assert (
        observed["D_mapped_joint_mass"]
        == observed["D_unmapped_joint_mass"]
        == {"numerator": 1, "denominator": 2}
    )


def test_unresolved_share_does_not_become_a_control_gate_or_valid_class(population):
    inputs, rule, projections, comparisons = population
    changed = copy.deepcopy(projections)
    index = next(i for i, item in enumerate(changed) if item["label"] == "S02")
    fields = {
        key: value for key, value in changed[index].items() if key not in {"id", "schema_version"}
    }
    fields.update(
        status="undetermined", supported=False, behavior_projection=None, control_evidence=True
    )
    changed[index] = record("panel_quotient_projection", **fields)
    pairs = [item for item in comparisons if item["task_group"] != "S"]
    with measurement_guard() as counts:
        result = run_controls(inputs, rule, changed, pairs)
        distribution = build_distribution(
            inputs["entries"], changed, pairs, inputs["measurement_condition"], rule
        )
    assert guard_report(counts, "unresolved_share_control_boundary")["all_zero"] is True
    assert result["all_expected_outcomes"] is True
    assert result["executed_control_count"] == 22 and result["not_applicable_control_count"] == 2
    cases = [row for row in result["rows"] if row["family"] == "retained_actual_behavior"]
    assert all(
        row["observed"]["outcome"] == "not_applicable_projection_undetermined" for row in cases
    )
    assert all(row["observed"]["comparison"] is None for row in cases)
    assert all(row["observed"]["behavior_difference_verified"] is None for row in cases)
    assert all(row["observed"]["projection_promoted"] is False for row in cases)
    share = next(row for row in distribution["task_distributions"] if row["task_group"] == "S")
    assert share["registered_session_count"] == 2 and share["qualified_count"] == 1
    assert share["conditional_distribution"] is None and share["unmapped_qualified_count"] == 1
    assert distribution["complete_panel_quotient_measurement_closed"] is False
    assert all(
        assignment["label"] not in {"S01", "S02"} for assignment in distribution["assignments"]
    )
