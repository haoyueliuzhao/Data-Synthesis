from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any

from trusted_synthesis.experiments.vtdo_experiment import (
    phase1_v26_capability_authoritative_parent_rejection_history as build_module,
)
from trusted_synthesis.experiments.vtdo_experiment import (
    phase1_v26_capability_authoritative_parent_rejection_history_models as models,
)

PACKAGE_ROOT = Path(__file__).resolve().parents[1]
FORMAL_DIR = Path(os.environ.get("V26_176_TEST_FORMAL_DIR", PACKAGE_ROOT / build_module.OUTPUT_DIR))


def _load(name: str) -> Any:
    return json.loads((FORMAL_DIR / name).read_text(encoding="utf-8"))


def test_formal_v26_176_chain_binds_and_blocks_the_audited_v175_surface() -> None:
    report = models.HardeningReport.model_validate(_load("report.json"))
    authorization = models.ExternalAuditAuthorization.model_validate(
        _load("external_audit_authorization.json")
    )
    predecessor = models.PredecessorFreezeAudit.model_validate(
        _load("v175_predecessor_freeze_audit.json")
    )
    defect = models.V175DefectReproductionAudit.model_validate(
        _load("v175_defect_reproduction_audit.json")
    )
    transition = models.ProspectiveTransition.model_validate(
        _load("prospective_transition_contract.json")
    )
    assert authorization.review_sha256 == build_module.EXPECTED_REVIEW_SHA256
    assert authorization.review_byte_count == build_module.EXPECTED_REVIEW_BYTE_COUNT == 22_178
    assert predecessor.predecessor_file_count == predecessor.independent_rebuild_match_count == 19
    assert predecessor.stale_runner_transition_blocked is True
    assert defect.accepted_runner_inherited_contract_attack_count == 4
    assert defect.accepted_development_public_task_attack_count == 1
    assert defect.accepted_development_inherited_contract_attack_count == 4
    assert defect.accepted_saved_replica_result_attack_count == 1
    assert defect.accepted_fully_rehashed_attack_count == 10
    assert defect.full_choice_combination_replica_count == 1
    assert defect.typed_rejection_feedback_persisted_count == 0
    assert report.provider_calls == report.development_jobs == 0
    assert transition.consumed_stage == models.AUTHORIZED_STAGE
    assert transition.next_stage == models.NEXT_STAGE
    assert transition.future_job_count == 192
    assert transition.provider_calls_authorized is False
    assert transition.development_jobs_authorized is False


def test_authoritative_development_and_runner_parents_reconstruct_and_replay() -> None:
    contract = models.AuthoritativePackageRunnerParentContract.model_validate(
        _load("authoritative_package_runner_parent_contract.json")
    )
    catalog = models.AuthoritativeDevelopmentCatalog.model_validate(
        _load("authoritative_development_catalog.json")
    )
    runner = models.AuthoritativeRunnerInputCatalog.model_validate(
        _load("authoritative_runner_input_catalog.json")
    )
    audit = models.AuthoritativeParentReconstructionAudit.model_validate(
        _load("authoritative_parent_reconstruction_audit.json")
    )
    assert contract.inherited_v174_contract_fields == build_module.INHERITED_CONTRACT_FIELDS
    assert contract.development_metadata_fields == build_module.DEVELOPMENT_METADATA_FIELDS
    assert contract.runner_metadata_fields == build_module.RUNNER_METADATA_FIELDS
    assert catalog.package_count == 32
    assert catalog.replica_result_count == 192
    assert audit.development_package_match_count == 32
    assert audit.development_metadata_field_match_count == 736
    assert audit.inherited_contract_package_match_count == 128
    assert audit.fresh_replica_replay_count == audit.fresh_replica_byte_match_count == 192
    assert audit.runner_package_match_count == 32
    assert audit.runner_metadata_field_match_count == 768
    assert audit.runner_inherited_contract_match_count == 128
    assert (
        audit.runner_missing_count == audit.runner_duplicate_count == audit.runner_extra_count == 0
    )
    assert runner.package_count == 32
    assert runner.future_job_count == 192
    assert runner.materialized_prompt_count == runner.materialized_observation_count == 0
    assert len({item.runner_package_id for item in runner.packages}) == 32
    assert len({item.source_development_package_artifact_id for item in runner.packages}) == 32


def test_all_required_fully_rehashed_parent_attacks_fail_closed() -> None:
    parent = models.AuthoritativeParentReconstructionAudit.model_validate(
        _load("authoritative_parent_reconstruction_audit.json")
    )
    destructive = models.ProductionDestructiveAudit.model_validate(
        _load("production_destructive_audit.json")
    )
    names = {item.mutation for item in parent.mutations}
    required = {
        "development_public_task_id_changed",
        "development_mechanism_semantics_contract_id_changed",
        "development_failure_receipt_contract_id_changed",
        "development_step_runtime_contract_id_changed",
        "development_sequential_estimand_contract_id_changed",
        "saved_replica_result_changed",
        "runner_mechanism_semantics_contract_id_changed",
        "runner_failure_receipt_contract_id_changed",
        "runner_step_runtime_contract_id_changed",
        "runner_sequential_estimand_contract_id_changed",
        "runner_duplicate_source_row",
    }
    assert required <= names
    assert parent.mutation_count == parent.rejection_count == len(parent.mutations) == 44
    assert parent.accepted_mutation_count == 0
    assert all(item.fully_rehashed and item.rejected for item in parent.mutations)
    assert destructive.mutation_count == destructive.rejection_count == 44
    assert destructive.acceptance_count == 0


def test_all_declared_choice_combinations_execute_in_all_six_replicas() -> None:
    audit = models.AllReplicaTrajectoryAudit.model_validate(
        _load("all_replica_trajectory_audit.json")
    )
    assert audit.package_count == 32
    assert audit.replica_count == 6
    assert audit.declared_combination_count_per_replica == 772
    assert audit.execution_count == len(audit.outcomes) == 4_632
    assert audit.reference_execution_count == 192
    assert audit.single_nonreference_execution_count == 876
    assert audit.multi_nonreference_execution_count == 3_564
    assert audit.fully_accepted_execution_count == 3_552
    assert audit.typed_rejected_execution_count == 1_080
    assert audit.base_valid_count == 432
    assert audit.mechanism_semantically_qualified_count == 528
    assert audit.qualified_valid_count == 432
    assert audit.semantic_outcome_replica_mismatch_count == 0
    assert audit.dependency_receipt_failure_count == 0
    assert audit.exact_failure_receipt_failure_count == 0
    assert audit.display_source_roundtrip_failure_count == 0
    assert audit.qualified_conjunction_mismatch_count == 0
    assert audit.runtime_exception_count == 0


def test_typed_rejection_is_visible_then_corrected_or_bounded_terminal() -> None:
    contract = models.TypedRejectionHistoryContract.model_validate(
        _load("typed_rejection_history_contract.json")
    )
    audit = models.TypedRejectionRecoveryAudit.model_validate(
        _load("typed_rejection_recovery_audit.json")
    )
    assert contract.corrected_response_attempt_bound == 1
    assert contract.first_rejection_must_parent_next_public_state is True
    assert contract.repeated_wrong_action_must_emit_typed_terminal is True
    assert contract.later_prompt_after_terminal_allowed is False
    assert audit.recovery_component_count == 20
    assert audit.replica_count == 6
    assert len(audit.rows) == audit.corrected_second_response_execution_count == 120
    assert audit.corrected_final_qualified_count == 120
    assert audit.repeated_wrong_action_execution_count == 120
    assert audit.repeated_wrong_typed_terminal_count == 120
    assert audit.model_visible_feedback_parent_match_count == 120
    assert audit.later_prompt_after_terminal_count == 0
    assert audit.rejection_retry_invocation_count == 0
    assert audit.rejection_tool_call_count == 0
    assert audit.rejection_component_advance_count == 0
    assert audit.hidden_parent_exposure_count == 0
    assert all(item.recovery_prompt_parent_match for item in audit.rows)
    assert all(item.corrected_final_qualified for item in audit.rows)
    assert all(item.repeated_wrong_terminal_emitted for item in audit.rows)
    assert all(item.later_prompt_blocked for item in audit.rows)


def test_all_noncompensatory_static_gates_pass() -> None:
    static = models.StaticAudit.model_validate(_load("static_audit.json"))
    source = models.TransitiveSourceRoot.model_validate(_load("transitive_source_root.json"))
    assert source.file_count == 328
    assert source.unresolved_import_count == 0
    assert static.gate_count == static.passed_gate_count == 28
    assert static.failed_gate_count == 0
    assert static.provider_calls == static.stage_2_provider_calls == 0
    assert static.development_jobs == static.confirmation_payload_access_count == 0
    assert static.mapper_call_count == static.state_assignment_count == 0
    assert static.frequency_row_count == 0
    assert all(item.passed for item in static.gates)


def test_empty_directory_rebuild_is_byte_identical_and_zero_call(tmp_path: Path) -> None:
    rebuilt = tmp_path / "v26_176_rebuilt"
    products = build_module.build(
        package_root=PACKAGE_ROOT,
        output_dir=rebuilt,
        external_audit_path=FORMAL_DIR / "external_parent_history_audit_input.txt",
    )
    assert products.report.provider_calls == 0
    assert products.report.development_jobs == 0
    expected = {item.name for item in FORMAL_DIR.iterdir() if item.is_file()}
    observed = {item.name for item in rebuilt.iterdir() if item.is_file()}
    assert len(expected) == len(observed) == 16
    assert observed == expected
    for name in sorted(expected):
        assert (rebuilt / name).read_bytes() == (FORMAL_DIR / name).read_bytes()
