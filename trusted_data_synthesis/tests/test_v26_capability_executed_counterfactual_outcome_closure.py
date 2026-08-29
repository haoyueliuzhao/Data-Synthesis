from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any

from trusted_synthesis.core.task.executed_counterfactual_outcome_closure import (
    REQUIRED_CAPABILITY_OUTCOME_FIELDS,
    CapabilityOutcomeRow,
)
from trusted_synthesis.experiments.vtdo_experiment import (
    phase1_v26_capability_executed_counterfactual_outcome_closure as build_module,
)
from trusted_synthesis.experiments.vtdo_experiment import (
    phase1_v26_capability_executed_counterfactual_outcome_closure_models as models,
)

PACKAGE_ROOT = Path(__file__).resolve().parents[1]
FORMAL_DIR = Path(os.environ.get("V26_178_TEST_FORMAL_DIR", PACKAGE_ROOT / build_module.OUTPUT_DIR))
PRELIMINARY_DIR = (
    PACKAGE_ROOT / "artifacts/vtdo_experiment/"
    "finance_v26_178_executed_counterfactual_outcome_closure_v1_20260830"
)


def _load(name: str) -> Any:
    return json.loads((FORMAL_DIR / name).read_text(encoding="utf-8"))


def test_formal_v26_178_chain_freezes_v177_and_blocks_runner_preflight() -> None:
    authorization = models.ExternalAuditAuthorization.model_validate(
        _load("external_audit_authorization.json")
    )
    predecessor = models.V177PredecessorFreezeAudit.model_validate(
        _load("v177_predecessor_freeze_audit.json")
    )
    transition = models.ProspectiveTransition.model_validate(
        _load("prospective_transition_contract.json")
    )
    report = models.ClosureReport.model_validate(_load("report.json"))
    assert authorization.review_sha256 == build_module.EXPECTED_REVIEW_SHA256
    assert authorization.review_byte_count == build_module.EXPECTED_REVIEW_BYTE_COUNT == 19_573
    assert predecessor.predecessor_file_count == 15
    assert predecessor.independent_rebuild_match_count == 15
    assert predecessor.predecessor_mutation_count == 0
    assert predecessor.blocked_runner_preflight_transition == models.BLOCKED_PREDECESSOR_STAGE
    assert transition.consumed_stage == models.AUTHORIZED_STAGE
    assert transition.blocked_predecessor_stage == models.BLOCKED_PREDECESSOR_STAGE
    assert transition.next_stage == models.NEXT_STAGE
    assert transition.current_manifest_count == transition.current_runner_count == 0
    assert transition.current_development_job_count == report.development_jobs == 0
    assert report.provider_calls == report.manifest_count == report.runner_count == 0
    assert report.empirical_outcome_row_count == 0
    assert report.detail_file_count == 13


def test_v177_evidence_names_are_downgraded_without_reclassifying_mechanisms() -> None:
    defect = models.V177EvidenceIdentityDefectAudit.model_validate(
        _load("v177_evidence_identity_defect_audit.json")
    )
    assert defect.old_projection_row_count == 432
    assert defect.old_host_counterfactual_declared_pass_count == 432
    assert defect.old_host_counterfactual_executed_count == 0
    assert defect.aliased_public_preimage_field_count == 3
    assert defect.host_counterfactual_measurement_failed is True
    assert defect.public_host_separation_property_falsified is False
    assert defect.old_registered_control_count == 312
    assert defect.old_registered_control_content_identity_rebuilt_count == 0
    assert defect.old_outcome_fixture_declared_count == 5
    assert defect.old_outcome_fixture_row_count == 0
    assert defect.old_outcome_eligibility_denominator_identified is False
    assert defect.old_fully_rehashed_outcome_erosion_attack_count == 0
    assert defect.historical_reclassification_count == 0


def test_complete_exact_catalog_scan_independently_derives_reachability() -> None:
    audit = models.ExactCatalogReachabilityAudit.model_validate(
        _load("exact_catalog_reachability_audit.json")
    )
    assert audit.package_count == 32
    assert audit.component_count == 80
    assert audit.state_scan_count == len(audit.state_rows) == 480
    assert audit.candidate_scan_count == 1_356
    assert audit.acceptance_count == 1_236
    assert audit.rejection_count == 120
    assert audit.registry_declaration_used_as_outcome_count == 0
    counts = {
        (item.decision_kind, item.rejection_code): item.observed_rejection_count
        for item in audit.reachability_rows
    }
    assert counts == {
        ("revise_selector", "typed_current_state_target_mismatch"): 120,
        ("revise_selector", "typed_failure_receipt_mismatch"): 0,
        ("reconcile_record", "typed_current_state_target_mismatch"): 0,
        ("consume_normalized_output", "typed_current_state_target_mismatch"): 0,
        ("assess_dynamic_readiness", "typed_current_state_target_mismatch"): 0,
    }
    assert audit.reachable_branch_count == 1
    assert audit.valid_object_unreachable_branch_count == 4


def test_registered_controls_are_canonical_valid_objects_and_execute_step_runtime() -> None:
    audit = models.ValidControlExecutionAudit.model_validate(
        _load("canonical_valid_control_execution_audit.json")
    )
    assert audit.control_object_count == len(audit.control_objects) == 72
    assert audit.execution_row_count == len(audit.rows) == 432
    assert audit.exact_catalog_execution_count == 120
    assert audit.canonical_diagnostic_execution_count == 312
    assert audit.rematerialized_component_execution_count == 192
    assert audit.valid_public_object_execution_count == 432
    assert audit.validation_bypass_count == 0
    assert audit.reference_correction_accept_count == 432
    assert audit.repeated_invalid_terminal_count == 432
    assert all(item.source_package_roundtrip_valid for item in audit.control_objects)
    assert all(item.component_roundtrip_valid for item in audit.control_objects)
    assert all(item.schedule_roundtrip_valid for item in audit.control_objects)
    assert all(item.runtime_exception_count == 0 for item in audit.rows)


def test_host_counterfactuals_are_executed_and_public_outputs_are_invariant() -> None:
    audit = models.ExecutedHostCounterfactualAudit.model_validate(
        _load("executed_host_counterfactual_audit.json")
    )
    assert audit.base_control_row_count == 432
    assert audit.intervention_kind_count == 7
    assert audit.intervention_execution_count == len(audit.rows) == 3_024
    assert audit.host_binding_change_count == 3_024
    assert audit.public_observation_invariance_count == 3_024
    assert audit.public_feedback_invariance_count == 3_024
    assert audit.recovery_prompt_invariance_count == 3_024
    assert audit.measurement_method == "executed_single_factor_and_joint_host_interventions"
    assert audit.public_preimage_boolean_reused_as_counterfactual_count == 0
    assert all(
        item.baseline_host_binding_id != item.counterfactual_host_binding_id for item in audit.rows
    )


def test_outcome_rows_roundtrip_and_share_the_frozen_192_job_denominator() -> None:
    contract = models.CapabilityOutcomeContract.model_validate(
        _load("capability_outcome_contract.json")
    )
    fixtures = models.OutcomeRowFixtureAudit.model_validate(_load("outcome_row_fixture_audit.json"))
    assert contract.package_count * contract.replica_count == 32 * 6
    assert contract.future_job_count == contract.eligible_job_count == 192
    assert contract.typed_exclusion_reasons == ()
    assert contract.post_outcome_exclusion_forbidden is True
    assert contract.outcome_fields == REQUIRED_CAPABILITY_OUTCOME_FIELDS
    assert contract.q_first_formula == "sum(first_attempt_qualified_valid)/192"
    assert contract.q_bounded_correction_formula == "sum(final_qualified_valid)/192"
    assert contract.materialized_manifest_count == 0
    assert fixtures.fixture_row_count == len(fixtures.rows) == 5
    assert fixtures.model_validation_roundtrip_count == 5
    assert fixtures.canonical_serialization_roundtrip_count == 5
    assert fixtures.fixture_q_first_numerator == 0
    assert fixtures.fixture_q_bounded_correction_numerator == 2
    assert fixtures.evaluation.q_first_fraction == "0/5"
    assert fixtures.evaluation.q_bounded_correction_fraction == "2/5"
    assert fixtures.empirical_row_count == 0
    assert all(
        CapabilityOutcomeRow.model_validate(item.model_dump()) == item for item in fixtures.rows
    )


def test_fully_rehashed_attacks_and_noncompensatory_gates_fail_closed() -> None:
    destructive = models.FullyRehashedDestructiveAudit.model_validate(
        _load("fully_rehashed_destructive_audit.json")
    )
    static = models.StaticAudit.model_validate(_load("static_audit.json"))
    source = models.TransitiveSourceRoot.model_validate(_load("transitive_source_root.json"))
    assert {item.mutation for item in destructive.mutations} == {
        "required_outcome_field_deletion",
        "eligibility_rule_replacement",
        "first_final_estimand_pooling",
        "host_counterfactual_boolean_alias",
        "registered_control_identity_bypass",
        "exact_reachability_status_relabeling",
    }
    assert destructive.mutation_count == destructive.rejection_count == 6
    assert destructive.acceptance_count == 0
    assert all(item.parent_identity_rehashed for item in destructive.mutations)
    assert all(item.transition_identity_rehashed for item in destructive.mutations)
    assert all(item.report_identity_rehashed for item in destructive.mutations)
    assert static.gate_count == static.passed_gate_count == 32
    assert static.failed_gate_count == 0
    assert static.provider_calls == static.stage_2_provider_calls == 0
    assert static.development_jobs == static.manifest_count == static.runner_count == 0
    assert source.file_count == 336
    assert source.unresolved_import_count == 0


def test_preliminary_v1_differs_only_in_implementation_bound_chain_files() -> None:
    authoritative_names = {item.name for item in FORMAL_DIR.iterdir() if item.is_file()}
    preliminary_names = {item.name for item in PRELIMINARY_DIR.iterdir() if item.is_file()}
    assert authoritative_names == preliminary_names
    differing = {
        name
        for name in authoritative_names
        if (FORMAL_DIR / name).read_bytes() != (PRELIMINARY_DIR / name).read_bytes()
    }
    assert differing == {
        "transitive_source_root.json",
        "prospective_transition_contract.json",
        "report.json",
    }


def test_empty_directory_warning_error_rebuild_is_byte_identical(tmp_path: Path) -> None:
    rebuilt = tmp_path / "v26_178_rebuilt"
    products = build_module.build(
        package_root=PACKAGE_ROOT,
        output_dir=rebuilt,
        external_audit_path=FORMAL_DIR / "external_v177_source_level_audit_input.txt",
    )
    assert products.report.provider_calls == 0
    assert products.report.development_jobs == 0
    expected = {item.name for item in FORMAL_DIR.iterdir() if item.is_file()}
    observed = {item.name for item in rebuilt.iterdir() if item.is_file()}
    assert len(expected) == len(observed) == 14
    assert observed == expected
    for name in sorted(expected):
        assert (rebuilt / name).read_bytes() == (FORMAL_DIR / name).read_bytes()
