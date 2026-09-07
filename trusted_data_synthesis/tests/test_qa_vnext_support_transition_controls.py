"""Small integration checks for the four new isolated measurement-control families."""

from __future__ import annotations

import copy
from pathlib import Path

import pytest

from trusted_synthesis.experiments.finance_qa_vnext_model_execution.models import record
from trusted_synthesis.experiments.finance_qa_vnext_support_transition.comparison import (
    compare_all,
    comparison_contract,
)
from trusted_synthesis.experiments.finance_qa_vnext_support_transition.controls import run_controls
from trusted_synthesis.experiments.finance_qa_vnext_support_transition.guards import (
    guard_report,
    measurement_guard,
)
from trusted_synthesis.experiments.finance_qa_vnext_support_transition.projection import (
    project_entry,
)
from trusted_synthesis.experiments.finance_qa_vnext_support_transition.rules import measurement_rule
from trusted_synthesis.experiments.finance_qa_vnext_support_transition.source import load_inputs
from trusted_synthesis.experiments.finance_qa_vnext_support_transition.stage import freeze_condition

ROOT = Path(__file__).resolve().parents[2]


@pytest.fixture(scope="module")
def population():
    with measurement_guard() as counts:
        inputs = load_inputs(ROOT)
        generation = inputs["generation_condition"]
        rule = measurement_rule()
        condition = freeze_condition(inputs, rule, record("implementation", isolated_test=True))
        contract = comparison_contract(condition, generation, rule)
        projections = [
            project_entry(entry, condition, generation, rule, contract)
            for entry in inputs["entries"]
        ]
        pairs = compare_all(inputs["entries"], projections, condition, generation, rule, contract)
    assert guard_report(counts, "controls_test_input")["all_zero"] is True
    return inputs, projections, pairs, condition, rule, contract


@pytest.fixture(scope="module")
def controlled(population):
    with measurement_guard() as counts:
        result = run_controls(*population)
    assert guard_report(counts, "controls_test_execution")["all_zero"] is True
    return result


def test_actual_twenty_two_controls_and_old_semantics_are_preserved(controlled):
    assert controlled["control_count"] == controlled["executed_control_count"] == 22
    assert controlled["not_applicable_control_count"] == 0
    assert controlled["family_counts"] == {
        "prior_semantics_compatibility": 2,
        "proposal_and_effect_boundary": 6,
        "actual_reconstruction_dependency": 6,
        "grounding_assertion_boundary": 3,
        "population_and_profile_boundary": 5,
    }
    assert controlled["all_expected_outcomes"] is True
    assert controlled["original_inputs_and_sidecars_unmodified"] is True
    assert all(row["passed"] and row["control_evidence"] for row in controlled["rows"])
    assert (
        controlled["counterfactual_valid_assignments_written"]
        == controlled["additional_model_trajectories"]
        == 0
    )
    assert (
        controlled["historical_input_loads"]
        == controlled["provider_calls"]
        == controlled["qualification_replays"]
        == 0
    )


def test_full_grounding_segment_not_just_four_wrong_citation_fragments(controlled):
    row = next(
        row
        for row in controlled["rows"]
        if row["name"] == "E02_entire_T9_T16_assertions_retained_without_new_uses_edges"
    )
    observed = row["observed"]
    assert observed["source_sequences"] == list(range(8, 16))
    assert len(observed["rows"]) == 8
    assert observed["intermediate_legacy_alignment_sequences"] == [9, 12, 14]
    assert observed["actual_nodes_byte_unchanged"] is True
    assert observed["assertions_are_not_actual_input_dependencies"] is True


def test_unrelated_undetermined_E02_preserves_witness_and_null_distribution(controlled):
    row = next(
        row
        for row in controlled["rows"]
        if row["name"] == "unresolved_E02_keeps_mass_and_does_not_erase_independent_DR_witness"
    )
    observed = row["observed"]
    assert observed["registered_denominator"] == 8 and observed["qualified_count"] == 3
    assert observed["conditional_distribution"] is None and observed["complete_class_count"] is None
    assert observed["W_support"] is True and observed["reference_DR_witness_established"] is True


def test_unsupported_E02_has_explicit_not_applicable_probes_without_promotion(population):
    inputs, projections, _, condition, rule, contract = population
    partial = copy.deepcopy(projections)
    index = next(i for i, item in enumerate(partial) if item["label"] == "E02")
    fields = {
        key: value for key, value in partial[index].items() if key not in {"id", "schema_version"}
    }
    fields.update(
        status="undetermined",
        supported=False,
        behavior_projection=None,
        interpretation_details=[],
        isolated_counterfactual=True,
        errors=[{"reason": "test_unresolved"}],
    )
    partial[index] = record("panel_quotient_projection", **fields)
    with measurement_guard() as counts:
        pairs = compare_all(
            inputs["entries"], partial, condition, inputs["generation_condition"], rule, contract
        )
        result = run_controls(inputs, partial, pairs, condition, rule, contract)
    assert guard_report(counts, "controls_unresolved_boundary")["all_zero"] is True
    assert result["all_expected_outcomes"] is True
    assert result["not_applicable_control_count"] == 2 and result["executed_control_count"] == 20
    skipped = [row for row in result["rows"] if row["observed"].get("test_executed") is False]
    assert all(row["observed"]["unresolved_projection_promoted"] is False for row in skipped)
    assert all(row["observed"]["semantic_proof_established"] is None for row in skipped)


def test_supported_E02_missing_required_segment_cannot_pass_as_not_applicable(population):
    inputs, projections, pairs, condition, rule, contract = population
    changed = copy.deepcopy(projections)
    index = next(i for i, item in enumerate(changed) if item["label"] == "E02")
    fields = {
        key: value for key, value in changed[index].items() if key not in {"id", "schema_version"}
    }
    fields.update(interpretation_details=[], isolated_counterfactual=True)
    changed[index] = record("panel_quotient_projection", **fields)
    with measurement_guard() as counts:
        result = run_controls(inputs, changed, pairs, condition, rule, contract)
    assert guard_report(counts, "controls_missing_segment_boundary")["all_zero"] is True
    assert result["all_expected_outcomes"] is False
    assert result["not_applicable_control_count"] == 0
    failed = [row for row in result["rows"] if not row["passed"]]
    assert len(failed) == 1
    assert failed[0]["observed"]["outcome"] == "missing_or_duplicate_required_grounding_segment"
