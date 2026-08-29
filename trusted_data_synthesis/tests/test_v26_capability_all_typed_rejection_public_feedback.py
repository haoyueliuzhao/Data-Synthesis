from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any

from trusted_synthesis.core.task.all_typed_rejection_public_feedback import (
    PROHIBITED_PUBLIC_FEEDBACK_KEYS,
    PUBLIC_FEEDBACK_FIELDS,
)
from trusted_synthesis.experiments.vtdo_experiment import (
    phase1_v26_capability_all_typed_rejection_public_feedback as build_module,
)
from trusted_synthesis.experiments.vtdo_experiment import (
    phase1_v26_capability_all_typed_rejection_public_feedback_models as models,
)

PACKAGE_ROOT = Path(__file__).resolve().parents[1]
FORMAL_DIR = Path(os.environ.get("V26_177_TEST_FORMAL_DIR", PACKAGE_ROOT / build_module.OUTPUT_DIR))


def _load(name: str) -> Any:
    return json.loads((FORMAL_DIR / name).read_text(encoding="utf-8"))


def test_formal_v26_177_chain_freezes_v176_and_blocks_its_runner_preflight() -> None:
    authorization = models.ExternalAuditAuthorization.model_validate(
        _load("external_audit_authorization.json")
    )
    predecessor = models.V176PredecessorFreezeAudit.model_validate(
        _load("v176_predecessor_freeze_audit.json")
    )
    transition = models.ProspectiveTransition.model_validate(
        _load("prospective_transition_contract.json")
    )
    report = models.ClosureReport.model_validate(_load("report.json"))
    assert authorization.review_sha256 == build_module.EXPECTED_REVIEW_SHA256
    assert authorization.review_byte_count == build_module.EXPECTED_REVIEW_BYTE_COUNT == 17_882
    assert predecessor.predecessor_file_count == 16
    assert predecessor.independent_rebuild_match_count == 16
    assert predecessor.predecessor_mutation_count == 0
    assert predecessor.blocked_runner_preflight_transition == models.BLOCKED_PREDECESSOR_STAGE
    assert transition.consumed_stage == models.AUTHORIZED_STAGE
    assert transition.blocked_predecessor_stage == models.BLOCKED_PREDECESSOR_STAGE
    assert transition.next_stage == models.NEXT_STAGE
    assert transition.current_manifest_count == transition.current_runner_count == 0
    assert transition.provider_calls_authorized is False
    assert transition.authorization_id == report.authorization_id
    assert transition.source_root_id == report.source_root_id
    assert transition.predecessor_freeze_audit_id == report.predecessor_freeze_audit_id
    assert transition.defect_reproduction_audit_id == report.defect_reproduction_audit_id
    assert transition.public_feedback_contract_id == report.public_feedback_contract_id
    assert transition.rejection_surface_catalog_id == report.rejection_surface_catalog_id
    assert (
        transition.public_feedback_projection_audit_id == report.public_feedback_projection_audit_id
    )
    assert transition.correction_matrix_audit_id == report.correction_matrix_audit_id
    assert transition.capability_outcome_contract_id == report.capability_outcome_contract_id
    assert transition.outcome_fixture_audit_id == report.outcome_fixture_audit_id
    assert transition.destructive_audit_id == report.destructive_audit_id
    assert transition.static_audit_id == report.static_audit_id
    assert report.provider_calls == report.development_jobs == 0


def test_public_feedback_schema_excludes_direct_and_derived_host_parents() -> None:
    defect = models.V176DefectReproductionAudit.model_validate(
        _load("v176_defect_reproduction_audit.json")
    )
    contract = models.PublicFeedbackContract.model_validate(
        _load("public_typed_rejection_feedback_contract.json")
    )
    projection = models.PublicFeedbackProjectionAudit.model_validate(
        _load("public_feedback_projection_audit.json")
    )
    assert defect.old_feedback_host_direct_fields == (
        "component_key",
        "selected_operation_hash",
        "action_acceptance_report_id",
    )
    assert defect.old_feedback_host_direct_field_count == 3
    assert defect.old_public_only_feedback_schema_proved is False
    assert contract.public_feedback_fields == PUBLIC_FEEDBACK_FIELDS
    assert set(contract.prohibited_public_fields) == set(PROHIBITED_PUBLIC_FEEDBACK_KEYS)
    assert contract.identity_preimage_policy == "strict_public_fields_only"
    assert contract.host_report_object_model_visible is False
    assert contract.host_report_identity_model_visible is False
    assert projection.projection_count == len(projection.rows) == 432
    assert projection.exact_catalog_projection_count == 120
    assert projection.registered_control_projection_count == 312
    assert projection.independent_projection_match_count == 432
    assert projection.host_counterfactual_invariant_count == 432
    assert projection.identity_preimage_public_only_count == 432
    assert projection.prohibited_key_count == 0
    assert projection.direct_hidden_scalar_exposure_count == 0
    assert projection.derived_host_identity_exposure_count == 0


def test_every_production_rejection_kind_is_registered_and_executed_as_control() -> None:
    surface = models.ProductionRejectionSurfaceCatalog.model_validate(
        _load("production_rejection_surface_catalog.json")
    )
    keys = {(item.decision_kind, item.rejection_code) for item in surface.rows}
    assert keys == {
        ("revise_selector", "typed_current_state_target_mismatch"),
        ("revise_selector", "typed_failure_receipt_mismatch"),
        ("reconcile_record", "typed_current_state_target_mismatch"),
        ("consume_normalized_output", "typed_current_state_target_mismatch"),
        ("assess_dynamic_readiness", "typed_current_state_target_mismatch"),
    }
    assert surface.decision_kind_count == 4
    assert surface.rejection_kind_count == 5
    assert surface.exact_catalog_reachable_kind_count == 1
    assert surface.registered_but_unreachable_kind_count == 4
    assert surface.unique_production_component_count == 52
    assert surface.registered_component_surface_count == 72
    assert surface.control_fixture_count == 432
    assert surface.exact_catalog_rejection_state_count == 120
    assert surface.silent_omission_count == 0
    assert all(item.control_rejection_count == item.control_fixture_count for item in surface.rows)
    assert all(
        item.reference_correction_accept_count == item.control_fixture_count
        for item in surface.rows
    )
    assert all(
        item.repeated_invalid_terminal_count == item.control_fixture_count for item in surface.rows
    )


def test_complete_second_response_matrix_is_bounded_and_nonreference_preserving() -> None:
    matrix = models.CorrectionBoundMatrixAudit.model_validate(
        _load("correction_bound_matrix_audit.json")
    )
    assert matrix.exact_initial_rejection_state_count == 120
    assert matrix.disposition_count == 7
    assert matrix.matrix_row_count == len(matrix.rows) == 840
    assert matrix.executed_row_count == 672
    assert matrix.registered_but_unreachable_row_count == 168
    assert matrix.reference_valid_accept_count == 120
    assert matrix.nonreference_valid_accept_count == 120
    assert matrix.same_invalid_terminal_count == 120
    assert matrix.different_current_invalid_unreachable_count == 120
    assert matrix.stale_terminal_count == 72
    assert matrix.stale_unreachable_count == 48
    assert matrix.foreign_terminal_count == 120
    assert matrix.malformed_abi_valid_terminal_count == 120
    assert matrix.any_second_invalid_terminal_count == 432
    assert matrix.later_correction_prompt_count == 0
    assert matrix.nonreference_direct_equivalence_count == 120
    assert matrix.final_or_terminal_lineage_binding_count == 672
    assert all(
        item.complete_rejection_lineage_bound is True
        for item in matrix.rows
        if item.availability == "executed"
    )


def test_first_attempt_and_bounded_correction_estimands_remain_separate() -> None:
    contract = models.CapabilityOutcomeContract.model_validate(
        _load("capability_outcome_contract.json")
    )
    fixture = models.OutcomeContractFixtureAudit.model_validate(
        _load("outcome_contract_fixture_audit.json")
    )
    assert contract.first_attempt_estimand == "q_first"
    assert contract.bounded_correction_estimand == "q_bounded_correction"
    assert contract.first_attempt_estimand != contract.bounded_correction_estimand
    assert contract.first_attempt_overwrite_forbidden is True
    assert contract.estimand_pooling_forbidden is True
    assert contract.future_job_count == 192
    assert contract.materialized_manifest_count == 0
    assert contract.empirical_outcome_row_count == 0
    assert fixture.fixture_count == fixture.first_attempt_failure_preserved_count == 5
    assert fixture.first_bounded_estimand_conflation_count == 0
    assert fixture.empirical_row_count == 0


def test_all_destructive_controls_and_noncompensatory_gates_pass() -> None:
    destructive = models.ProductionDestructiveAudit.model_validate(
        _load("production_destructive_audit.json")
    )
    static = models.StaticAudit.model_validate(_load("static_audit.json"))
    source = models.TransitiveSourceRoot.model_validate(_load("transitive_source_root.json"))
    required_mutations = {
        "public_feedback_extra_package_id",
        "public_feedback_extra_component_key",
        "public_feedback_extra_selected_operation_hash",
        "public_feedback_extra_acceptance_report_id",
        "second_feedback_missing_public_predecessor",
        "terminal_allows_later_prompt",
        "production_rejection_kind_silently_dropped",
        "accepted_correction_zero_commit",
        "unreachable_correction_missing_reason",
        "nonreference_direct_equivalence_falsified",
    }
    assert required_mutations <= {item.mutation for item in destructive.mutations}
    assert destructive.mutation_count == destructive.rejection_count == 26
    assert destructive.acceptance_count == 0
    assert static.gate_count == static.passed_gate_count == 30
    assert static.failed_gate_count == 0
    assert static.provider_calls == static.stage_2_provider_calls == 0
    assert static.development_jobs == static.manifest_count == static.runner_count == 0
    assert source.unresolved_import_count == 0
    assert source.file_count > 328


def test_empty_directory_rebuild_is_byte_identical_and_zero_call(tmp_path: Path) -> None:
    rebuilt = tmp_path / "v26_177_rebuilt"
    products = build_module.build(
        package_root=PACKAGE_ROOT,
        output_dir=rebuilt,
        external_audit_path=FORMAL_DIR / "external_v176_revision_audit_input.txt",
    )
    assert products.report.provider_calls == 0
    assert products.report.development_jobs == 0
    expected = {item.name for item in FORMAL_DIR.iterdir() if item.is_file()}
    observed = {item.name for item in rebuilt.iterdir() if item.is_file()}
    assert len(expected) == len(observed) == 15
    assert observed == expected
    for name in sorted(expected):
        assert (rebuilt / name).read_bytes() == (FORMAL_DIR / name).read_bytes()
