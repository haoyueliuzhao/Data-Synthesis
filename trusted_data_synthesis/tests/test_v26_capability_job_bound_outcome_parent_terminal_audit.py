from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any

from trusted_synthesis.experiments.vtdo_experiment import (
    phase1_v26_capability_job_bound_outcome_parent_terminal_audit as build_module,
)
from trusted_synthesis.experiments.vtdo_experiment import (
    phase1_v26_capability_job_bound_outcome_parent_terminal_audit_models as models,
)

PACKAGE_ROOT = Path(__file__).resolve().parents[1]
FORMAL_DIR = Path(os.environ.get("V26_180_TEST_FORMAL_DIR", PACKAGE_ROOT / build_module.OUTPUT_DIR))


def _load(name: str) -> Any:
    return json.loads((FORMAL_DIR / name).read_text(encoding="utf-8"))


def test_external_authorization_freezes_and_rebuilds_v179() -> None:
    authorization = models.ExternalAuditAuthorization.model_validate(
        _load("external_audit_authorization.json")
    )
    predecessor = models.V179PredecessorFreezeAudit.model_validate(
        _load("v179_predecessor_freeze_audit.json")
    )
    claim = models.V179ClaimScopeAudit.model_validate(_load("v179_claim_scope_audit.json"))
    assert authorization.review_sha256 == build_module.EXPECTED_REVIEW_SHA256
    assert authorization.review_byte_count == build_module.EXPECTED_REVIEW_BYTE_COUNT == 22_294
    assert authorization.audited_commit == build_module.AUDITED_COMMIT
    assert authorization.consumed_stage == models.CONSUMED_STAGE
    assert authorization.provider_execution_authorized is False
    assert predecessor.predecessor_file_count == 18
    assert predecessor.independent_rebuild_match_count == 18
    assert predecessor.predecessor_mutation_count == 0
    assert claim.local_scripted_runner_preflight_retained is True
    assert claim.exact_prospective_job_index_set_retained is True
    assert claim.strongest_estimator_claim == (
        "exact_job_key_set_and_wrapper_parent_estimator_gate"
    )
    assert claim.exact_job_outcome_evidence_set_closed is False
    assert claim.online_development_execution_authorized is False


def test_six_fully_rehashed_parent_authenticity_attacks_are_accepted() -> None:
    audit = models.ParentAuthenticityAudit.model_validate(
        _load("empirical_parent_authenticity_audit.json")
    )
    assert audit.attack_count == audit.current_estimator_acceptance_count == 6
    assert audit.defect_reproduction_count == 6
    assert audit.exact_job_index_set_closed is True
    assert audit.exact_job_outcome_evidence_set_closed is False
    assert audit.formal_empirical_outcome_row_count == 0
    assert audit.formal_empirical_estimate_count == 0
    by_name = {item.attack_name: item for item in audit.attacks}
    assert set(by_name) == {
        "cross_job_outcome_payload_reassignment",
        "duplicate_raw_execution_id_across_jobs",
        "duplicate_result_id_across_jobs",
        "swapped_raw_and_result_parents",
        "result_parent_outcome_final_mismatch",
        "duplicate_attempt_trace_across_jobs",
    }
    assert all(item.row_count == item.fully_rehashed_row_count == 192 for item in audit.attacks)
    assert all(
        item.unique_row_id_count == item.unique_job_id_count == 192 for item in audit.attacks
    )
    assert all(item.current_estimator_accepted for item in audit.attacks)
    assert by_name["duplicate_raw_execution_id_across_jobs"].unique_raw_execution_id_count == 1
    assert by_name["duplicate_result_id_across_jobs"].unique_result_id_count == 1
    assert by_name["duplicate_attempt_trace_across_jobs"].unique_attempt_trace_id_count == 1


def test_final_and_first_action_runtime_paths_are_not_total() -> None:
    final = models.FinalAbiTotalityAudit.model_validate(
        _load("final_abi_terminal_totality_audit.json")
    )
    first = models.FirstActionReferenceTotalityAudit.model_validate(
        _load("first_action_reference_totality_audit.json")
    )
    assert final.control_indices == (7, 8)
    assert final.final_abi_false_qualified_payload_accepted is True
    assert final.final_response_abi_invalid_endpoint_registered is False
    assert final.invalid_final_parser_rejected is True
    assert final.production_runner_final_parser_invocation_count == 1
    assert final.production_runner_returned_trace is False
    assert final.typed_final_abi_invalid_outcome_count == final.exact_outcome_row_count == 0
    assert final.verifier_null_policy_proven is False
    assert final.qualified_false_policy_proven is False
    assert first.control_index == 9
    assert len(first.unknown_action_id) == 24
    assert first.action_abi_valid is True
    assert first.response_state_matches_current_state is True
    assert first.action_absent_from_current_candidates is True
    assert first.first_action_reference_invalid_endpoint_registered is False
    assert first.production_runner_raised is True
    assert first.production_runner_exception_message == (
        "ABI-valid first response references an absent current Action"
    )
    assert first.typed_outcome_count == first.exact_outcome_row_count == 0
    assert first.correction_policy_frozen is False


def test_failure_fields_and_outer_endpoints_remain_unclosed() -> None:
    failure = models.FailureFieldSemanticsAudit.model_validate(
        _load("failure_field_semantics_audit.json")
    )
    outer = models.OuterTerminalTotalityAudit.model_validate(
        _load("outer_terminal_totality_audit.json")
    )
    assert failure.control_index == 10
    assert failure.all_components_committed is True
    assert failure.expected_first_uncommitted_component_key is None
    assert failure.fully_rehashed_payload_accepted is True
    assert failure.first_uncommitted_component_key_field_present is False
    assert failure.first_mechanism_failed_component_key_field_present is False
    assert failure.old_field_has_runtime_mechanism_fallback is True
    assert failure.strict_failure_field_semantics_closed is False
    assert outer.control_index == 11
    assert outer.endpoint_class_count == outer.missing_exact_outcome_row_count == 6
    assert outer.registered_endpoint_count == outer.exact_outcome_row_count == 0
    assert outer.terminal_totality_closed is False
    assert {item.endpoint_kind for item in outer.rows} == set(build_module.OUTER_ENDPOINTS)
    assert all(not item.endpoint_registered_in_v179 for item in outer.rows)
    assert all(not item.job_bound_payload_constructible for item in outer.rows)
    assert all(not item.exact_outcome_row_constructible for item in outer.rows)


def test_static_audit_passes_while_online_gate_fails_closed() -> None:
    source = models.TransitiveSourceRoot.model_validate(_load("transitive_source_root.json"))
    static = models.StaticAudit.model_validate(_load("static_audit.json"))
    gate = models.OnlineExecutionGate.model_validate(_load("online_execution_gate.json"))
    transition = models.ProspectiveTransition.model_validate(
        _load("prospective_transition_contract.json")
    )
    report = models.AuditReport.model_validate(_load("report.json"))
    assert source.unresolved_import_count == 0
    assert static.gate_count == static.passed_gate_count == 25
    assert static.failed_gate_count == 0
    assert static.registered_defect_control_count == 11
    assert static.reproduced_defect_control_count == 11
    assert static.provider_calls == static.development_model_outcomes == 0
    assert gate.decision == models.FAILED_DECISION
    assert gate.exact_job_index_set_closed is True
    assert gate.exact_job_outcome_evidence_set_closed is False
    assert gate.empirical_outcome_parent_authenticity_closed is False
    assert gate.online_terminal_totality_closed is False
    assert gate.online_development_execution_authorized is False
    assert transition.consumed_stage == models.CONSUMED_STAGE
    assert transition.decision == models.FAILED_DECISION
    assert transition.next_stage == models.NEXT_STAGE
    assert len(transition.permitted_change_surface) == 9
    assert transition.provider_execution_authorized is False
    assert transition.source_task_component_candidate_change_authorized is False
    assert report.detail_file_count == 13
    assert report.registered_defect_control_count == 11
    assert report.reproduced_defect_control_count == 11
    assert report.exact_job_index_count == 192
    assert report.empirical_outcome_row_count == report.empirical_estimate_count == 0
    assert report.provider_calls == report.development_model_outcomes == 0
    assert report.online_execution_authorized is False
    assert report.decision == models.FAILED_DECISION
    assert report.next_stage == models.NEXT_STAGE


def test_empty_directory_warning_error_rebuild_is_byte_identical(tmp_path: Path) -> None:
    rebuilt = tmp_path / "v26_180_rebuilt"
    products = build_module.build(
        package_root=PACKAGE_ROOT,
        output_dir=rebuilt,
        external_audit_path=FORMAL_DIR / "external_v179_revision_result_audit.txt",
    )
    assert products.report.provider_calls == 0
    assert products.report.empirical_outcome_row_count == 0
    assert products.online_gate.online_development_execution_authorized is False
    expected = {item.name for item in FORMAL_DIR.iterdir() if item.is_file()}
    observed = {item.name for item in rebuilt.iterdir() if item.is_file()}
    assert len(expected) == len(observed) == 14
    assert observed == expected
    for name in sorted(expected):
        assert (rebuilt / name).read_bytes() == (FORMAL_DIR / name).read_bytes()
