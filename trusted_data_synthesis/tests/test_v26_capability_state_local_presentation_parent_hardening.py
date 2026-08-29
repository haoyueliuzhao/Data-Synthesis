from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any

from trusted_synthesis.core.task.state_local_presentation_hardening import (
    schedule_codebook_signature,
    state_local_factorization_holds,
)
from trusted_synthesis.experiments.vtdo_experiment import (
    phase1_v26_capability_state_local_presentation_parent_hardening as build_module,
)
from trusted_synthesis.experiments.vtdo_experiment import (
    phase1_v26_capability_state_local_presentation_parent_hardening_models as models,
)

PACKAGE_ROOT = Path(__file__).resolve().parents[1]
FORMAL_DIR = Path(os.environ.get("V26_175_TEST_FORMAL_DIR", PACKAGE_ROOT / build_module.OUTPUT_DIR))


def _load(name: str) -> Any:
    return json.loads((FORMAL_DIR / name).read_text(encoding="utf-8"))


def test_formal_v26_175_chain_consumes_only_the_authorized_zero_call_stage() -> None:
    report = models.HardeningReport.model_validate(_load("report.json"))
    authorization = models.ExternalAuditAuthorization.model_validate(
        _load("external_audit_authorization.json")
    )
    predecessor = models.PredecessorFreezeAudit.model_validate(
        _load("v174_predecessor_freeze_audit.json")
    )
    defect = models.V174DefectReproductionAudit.model_validate(
        _load("v174_defect_reproduction_audit.json")
    )
    transition = models.ProspectiveTransition.model_validate(
        _load("prospective_transition_contract.json")
    )
    assert authorization.review_sha256 == build_module.EXPECTED_REVIEW_SHA256
    assert authorization.review_byte_count == build_module.EXPECTED_REVIEW_BYTE_COUNT == 22_189
    assert predecessor.predecessor_file_count == predecessor.independent_rebuild_match_count == 23
    assert defect.triple_rank_attack_recovery_count == 396
    assert defect.legal_single_choice_nonreference_execution_count == 146
    assert defect.full_multicomponent_combination_audited is False
    assert defect.accepted_rehashed_source_v173_catalog_parent_attack_count == 1
    assert defect.accepted_rehashed_source_v171_catalog_parent_attack_count == 1
    assert defect.classifier_only_receipt_mutation_count == 120
    assert defect.production_step_receipt_mutation_count == 0
    assert report.provider_calls == report.stage2_provider_calls == report.development_jobs == 0
    assert report.confirmation_payload_access_count == report.mapper_calls == 0
    assert transition.consumed_stage == models.AUTHORIZED_STAGE
    assert transition.next_stage == models.NEXT_STAGE
    assert transition.provider_calls_authorized is False
    assert transition.development_jobs_authorized is False


def test_state_local_schedules_close_registered_pairwise_and_triple_rank_rules() -> None:
    schedules = models.StateLocalScheduleCatalog.model_validate(
        _load("state_local_schedule_catalog.json")
    )
    audit = models.HigherOrderPresentationAudit.model_validate(
        _load("higher_order_presentation_audit.json")
    )
    assert schedules.schedule_count == schedules.unique_schedule_id_count == 80
    assert schedules.unique_codebook_count == 80
    assert schedules.reused_codebook_count == 0
    assert schedules.reference_first_normalization_count == 0
    assert len({schedule_codebook_signature(item) for item in schedules.schedules}) == 80
    assert all(state_local_factorization_holds(item) for item in schedules.schedules)
    assert audit.stratum_count == 80
    assert audit.presentation_count == 480
    assert audit.three_choice_state_count == 66
    assert audit.predecessor_explicit_attack_recovery_count == 396
    assert audit.current_explicit_attack_recovery_count == 116
    assert audit.current_explicit_attack_recovery_count <= audit.current_structural_baseline_total
    assert audit.current_structural_baseline_total == 132
    assert audit.registered_univariate_pairwise_rule_evaluation_count == 23_918
    assert audit.registered_triple_affine_rule_evaluation_count == 14_865_120
    assert audit.excess_stratum_count == 0
    for stratum in audit.strata:
        assert stratum.maximum_triple_rule_success_count <= (
            stratum.structural_baseline_success_count
        )
        assert stratum.explicit_counterexample_success_count <= (
            stratum.structural_baseline_success_count
        )


def test_complete_choice_cartesian_surface_includes_multicomponent_interactions() -> None:
    audit = models.ExhaustiveTrajectoryInteractionAudit.model_validate(
        _load("exhaustive_trajectory_interaction_audit.json")
    )
    assert audit.package_count == 32
    assert audit.declared_combination_count == 772
    assert audit.maximum_package_combination_count == 81
    assert audit.fully_accepted_combination_count == 592
    assert audit.typed_rejected_combination_count == 180
    assert audit.reference_combination_count == audit.reference_qualified_count == 32
    assert audit.legal_single_choice_nonreference_combination_count == 146
    assert audit.multi_nonreference_combination_count == 594
    assert audit.multi_nonreference_fully_accepted_count == 434
    assert audit.base_valid_count == 72
    assert audit.mechanism_semantically_qualified_count == 88
    assert audit.qualified_valid_count == 72
    assert audit.qualified_conjunction_mismatch_count == 0
    assert audit.dependency_receipt_failure_count == 0
    assert audit.exact_failure_receipt_failure_count == 0
    assert audit.runtime_exception_count == 0
    for row in audit.rows:
        if row.all_actions_accepted:
            assert row.qualified_valid == (row.base_valid and row.mechanism_semantically_qualified)
        else:
            assert row.typed_rejection is True
            assert row.first_failed_component_key is not None
            assert row.committed_component_count < row.target_component_count


def test_receipt_mutations_execute_production_step_without_retry_or_advancement() -> None:
    audit = models.RuntimeReceiptMutationAudit.model_validate(
        _load("runtime_receipt_mutation_audit.json")
    )
    assert audit.recovery_component_count == 20
    assert audit.mutation_kind_count == 6
    assert audit.production_step_execution_count == audit.typed_rejection_count == 120
    assert audit.retry_invocation_count == 0
    assert audit.recovery_success_event_count == 0
    assert audit.local_tool_invocation_count == 0
    assert audit.target_component_advance_count == 0
    assert audit.next_target_component_advance_count == 0
    assert {item.mutation for item in audit.executions} == {
        "error",
        "missing",
        "receipt_id",
        "rule",
        "selector",
        "tool",
    }
    assert all(item.typed_rejected for item in audit.executions)
    assert all(not item.target_component_advanced for item in audit.executions)
    assert all(item.exact_failure_event_retained for item in audit.executions)


def test_source_catalog_runner_and_schedule_parents_fail_closed() -> None:
    source_parent = models.SourceCatalogParentAudit.model_validate(
        _load("source_catalog_parent_audit.json")
    )
    parent = models.ParentClosureAudit.model_validate(_load("parent_closure_audit.json"))
    runner = models.StateLocalRunnerInputCatalog.model_validate(
        _load("state_local_runner_input_catalog.json")
    )
    destructive = models.ProductionDestructiveAudit.model_validate(
        _load("production_destructive_audit.json")
    )
    assert source_parent.source_v174_catalog_match is True
    assert source_parent.source_v173_catalog_match is True
    assert source_parent.source_v171_catalog_match is True
    assert source_parent.fully_rehashed_top_level_attack_count == 3
    assert source_parent.fully_rehashed_top_level_rejection_count == 3
    assert parent.development_package_reconstruction_match_count == 32
    assert parent.schedule_reconstruction_match_count == 80
    assert parent.runner_package_reconstruction_match_count == 32
    assert parent.fully_rehashed_mutation_count == parent.fully_rehashed_rejection_count == 8
    assert parent.accepted_mutation_count == 0
    assert runner.package_count == 32
    assert runner.future_job_count == 192
    assert runner.materialized_prompt_count == runner.materialized_observation_count == 0
    assert len({item.package_id for item in runner.packages}) == 32
    assert len({item.source_development_package_artifact_id for item in runner.packages}) == 32
    assert destructive.mutation_count == destructive.rejection_count == 20
    assert destructive.acceptance_count == 0


def test_all_noncompensatory_static_gates_pass() -> None:
    static = models.StaticAudit.model_validate(_load("static_audit.json"))
    assert static.gate_count == static.passed_gate_count == 23
    assert static.failed_gate_count == 0
    assert static.provider_calls == static.development_jobs == 0
    assert static.confirmation_payload_access_count == 0
    assert all(item.passed for item in static.gates)


def test_empty_directory_rebuild_is_byte_identical_and_zero_call(tmp_path: Path) -> None:
    rebuilt = tmp_path / "v26_175_rebuilt"
    products = build_module.build(
        package_root=PACKAGE_ROOT,
        output_dir=rebuilt,
        external_audit_path=FORMAL_DIR / "external_joint_audit_input.txt",
    )
    assert products.report.provider_calls == 0
    assert products.report.development_jobs == 0
    expected = {item.name for item in FORMAL_DIR.iterdir() if item.is_file()}
    observed = {item.name for item in rebuilt.iterdir() if item.is_file()}
    assert len(expected) == len(observed) == 19
    assert observed == expected
    for name in sorted(expected):
        assert (rebuilt / name).read_bytes() == (FORMAL_DIR / name).read_bytes()
