"""Pure report-label checks: no Student tensors, loss, API, or GPU are inspected."""

import pytest

from trusted_synthesis.finance_research.v8_training_driver import material_report_identity


@pytest.mark.parametrize(
    "schema,version",
    [
        ("v17_three_task_complete_material_binding.v1", "v17"),
        ("v16_six_task_complete_material_binding.v1", "v16"),
        ("v15_complete_material_binding.v1", "v15"),
        ("v14_material_binding.v1", "v14"),
    ],
)
def test_successor_state_sources_keep_actual_original_v14_supervision(schema, version):
    assert material_report_identity(schema) == (
        version,
        "v14_state_independent_original_span_union.v1",
    )


@pytest.mark.parametrize(
    "schema,expected",
    [
        ("v13_material_binding.v1", ("v13", "v13_fixed_authority_original_spans.v1")),
        ("v10_material_binding.v1", ("v10", "v10_single_authority_original_spans.v1")),
        (None, ("v8", "v8_single_authoritative_targets.v1")),
    ],
)
def test_existing_report_labels_are_unchanged(schema, expected):
    assert material_report_identity(schema) == expected
