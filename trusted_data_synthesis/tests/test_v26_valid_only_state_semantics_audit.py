from __future__ import annotations

import hashlib
from pathlib import Path

from trusted_synthesis.experiments.vtdo_experiment import (
    phase1_v26_valid_only_state_semantics_audit as state_semantics,
)


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def test_v26_159_zero_call_audit_reproduces_all_semantic_diagnostics(tmp_path: Path) -> None:
    package_root = Path(__file__).resolve().parents[1]
    historical_paths = (
        package_root / state_semantics.DEFAULT_MAPPING_EXECUTION_DIR / "report.json",
        package_root / state_semantics.DEFAULT_MAPPING_POSTRUN_DIR / "report.json",
    )
    before = tuple(_sha256(path) for path in historical_paths)

    first = state_semantics.build_state_semantics_audit(
        implementation_root=package_root,
        output_dir=tmp_path / "first",
    )
    state_semantics.build_state_semantics_audit(
        implementation_root=package_root,
        output_dir=tmp_path / "second",
    )

    first_files = tuple(sorted(path.name for path in (tmp_path / "first").iterdir()))
    second_files = tuple(sorted(path.name for path in (tmp_path / "second").iterdir()))
    assert first_files == second_files
    assert all(
        (tmp_path / "first" / name).read_bytes() == (tmp_path / "second" / name).read_bytes()
        for name in first_files
    )
    assert tuple(_sha256(path) for path in historical_paths) == before

    assert first.report.report_id == (
        "finance_v26_state_semantics_audit_report:"
        "1af922c296dba8df78cec0082178e0e913d8ad228bb3b95dfe7371b06b73fd08"
    )
    assert first.report.provider_calls == 0
    assert first.report.formal_new_state_assignment_count == 0
    assert first.report.historical_reclassified is False
    assert first.result_semantics.raw_vs_verifier_canonical_result_difference_count == 45
    assert first.result_semantics.mapper_v1_states_in_result_only_merge_groups == 14
    assert first.result_semantics.assignments_in_result_only_merge_groups == 40
    assert first.result_semantics.minimal_result_only_equivalence_class_count == 34
    assert first.condition_route.experimental_condition_id_count == 29
    assert first.condition_route.task_pre_treatment_condition_cell_count == 37
    assert first.report.experimental_condition_count == 29
    assert first.report.task_condition_cell_count == 37
    assert first.condition_route.fixed_condition_cells_split_by_mapper_v1_route_count == 9
    assert first.condition_route.unconditional_task_condition_cell_count == 9
    assert first.condition_route.unconditional_cells_split_by_mapper_v1_route_count == 3
    assert first.fixed_condition_support.source_population_task_count == 12
    assert first.fixed_condition_support.qualified_task_count == 10
    assert first.fixed_condition_support.mapper_v1_pooled_multiple_state_task_count == 10
    assert (
        first.fixed_condition_support.mapper_v1_any_fixed_condition_multiple_state_task_count == 8
    )
    assert first.fixed_condition_support.mapper_v1_unconditional_multiple_state_task_count == 4
    assert first.fixed_condition_support.result_only_pooled_multiple_state_task_count == 9
    assert (
        first.fixed_condition_support.result_only_any_fixed_condition_multiple_state_task_count == 8
    )
    assert first.fixed_condition_support.result_only_unconditional_multiple_state_task_count == 3
    assert first.diagnostic_catalog.mapper_v2_diagnostic_state_count == 41
    assert first.diagnostic_catalog.v1_states_merged_by_v2_count == 12
    assert first.diagnostic_catalog.v1_states_split_by_v2_count == 5
    assert first.gold_fixture_audit.production_pass_count == 5
    assert first.reference_audit.exact_state_match_count == 100
    assert first.contrast_catalog.contrast_count == 820
    assert first.classification_audit.historical_support_exit_count == 4
    assert (
        first.classification_audit.historical_support_exit_reprojected_as_instrument_failure_count
        == 4
    )
    assert first.classification_audit.v2_support_instrument_overlap_count == 0
    assert first.classification_audit.v2_typed_rejection_validity_evaluable_count == 1
    assert first.destructive_audit.failed_closed_count == 12
    assert first.transition.provider_execution_authorized is False
    assert first.transition.current_historical_frequency_authorized is False


def test_v26_159_diagnostic_assignments_bind_content_condition_and_route(tmp_path: Path) -> None:
    package_root = Path(__file__).resolve().parents[1]
    products = state_semantics.build_state_semantics_audit(
        implementation_root=package_root,
        output_dir=tmp_path / "audit",
    )

    assert len(products.diagnostic_assignments) == 100
    assert all(item.valid_only_gate_crossed for item in products.diagnostic_assignments)
    assert all(not item.historical_reclassified for item in products.diagnostic_assignments)
    assert all(not item.frequency_authorized for item in products.diagnostic_assignments)
    assert all(
        item.experimental_condition.contains_post_treatment_model_behavior is False
        for item in products.diagnostic_assignments
    )
    assert all(
        item.empirical_route_signature.contains_pre_treatment_condition is False
        for item in products.diagnostic_assignments
    )
    assert len({item.experimental_condition_id for item in products.diagnostic_assignments}) == 29
    assert (
        len({item.empirical_route_signature_id for item in products.diagnostic_assignments}) == 44
    )
