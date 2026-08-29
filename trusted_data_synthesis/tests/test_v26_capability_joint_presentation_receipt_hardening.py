from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any

from trusted_synthesis.core.task.joint_presentation_receipt_hardening import (
    resolve_encoded_operation,
)
from trusted_synthesis.experiments.vtdo_experiment import (
    phase1_v26_capability_joint_presentation_receipt_hardening as build_module,
)
from trusted_synthesis.experiments.vtdo_experiment import (
    phase1_v26_capability_joint_presentation_receipt_hardening_models as models,
)

PACKAGE_ROOT = Path(__file__).resolve().parents[1]
FORMAL_DIR = Path(os.environ.get("V26_174_TEST_FORMAL_DIR", PACKAGE_ROOT / build_module.OUTPUT_DIR))


def _load(name: str) -> Any:
    return json.loads((FORMAL_DIR / name).read_text(encoding="utf-8"))


def _catalog() -> models.HardenedDevelopmentCatalog:
    return models.HardenedDevelopmentCatalog.model_validate(
        _load("hardened_development_catalog.json")
    )


def _packages() -> tuple[models.HardenedDevelopmentPackage, ...]:
    return tuple(item for group in _catalog().groups for item in group.packages)


def test_formal_v26_174_chain_consumes_only_the_zero_call_hardening_stage() -> None:
    report = models.HardeningReport.model_validate(_load("report.json"))
    authorization = models.ExternalAuditAuthorization.model_validate(
        _load("external_audit_authorization.json")
    )
    predecessor = models.PredecessorFreezeAudit.model_validate(
        _load("v173_predecessor_freeze_audit.json")
    )
    defect = models.V173DefectReproductionAudit.model_validate(
        _load("v173_defect_reproduction_audit.json")
    )
    static = models.StaticAudit.model_validate(_load("static_audit.json"))
    transition = models.ProspectiveTransition.model_validate(
        _load("prospective_transition_contract.json")
    )
    assert authorization.review_sha256 == build_module.EXPECTED_REVIEW_SHA256
    assert authorization.review_byte_count == build_module.EXPECTED_REVIEW_BYTE_COUNT
    assert predecessor.file_count == predecessor.independent_rebuild_match_count == 21
    assert defect.three_choice_state_count == 66
    assert defect.two_choice_state_count == 14
    assert defect.action_rank_candidate_position_recovery_count == 396
    assert defect.display_rank_legend_position_recovery_count == 396
    assert defect.legal_nonreference_execution_count == 146
    assert defect.nonreference_mechanism_qualified_count == 0
    assert defect.prompt_runtime_receipt_identity_match_count == 0
    assert defect.runtime_internal_receipt_lineage_count == 120
    assert defect.accepted_development_parent_rehash_count == 6
    assert defect.accepted_runner_parent_rehash_count == 7
    assert defect.duplicate_drop_runner_denominator_accepted is True
    assert static.passed_gate_count == static.gate_count == 18
    assert report.provider_calls == report.development_jobs == 0
    assert transition.blocked_predecessor_stage == (
        "capability_observation_state_bound_step_runtime_development_runner_preflight_only"
    )
    assert transition.next_stage == models.NEXT_STAGE
    assert transition.provider_calls_authorized is False
    assert transition.development_jobs_authorized is False


def test_joint_rank_rules_stay_below_every_exact_stratum_baseline() -> None:
    audit = models.JointShortcutAudit.model_validate(_load("joint_shortcut_audit.json"))
    assert audit.stratum_count == audit.target_state_count == 80
    assert audit.presentation_count == 480
    assert audit.displayed_candidate_count == 1356
    assert audit.evaluated_rule_count == 23918
    assert audit.excess_stratum_count == 0
    assert audit.predecessor_action_rank_candidate_position_recovery_count == 396
    assert audit.predecessor_display_rank_legend_position_recovery_count == 396
    assert audit.current_action_rank_candidate_position_recovery_count == 0
    assert audit.current_display_rank_legend_position_recovery_count == 0
    assert audit.stable_cross_replica_value_vector_count == 0
    assert audit.unique_encoded_operation_length_presentation_count == 0
    assert audit.action_id_rank_imbalance_count == 0
    assert audit.value_handle_rank_imbalance_count == 0
    assert audit.visible_padding_field_count == 0
    for stratum in audit.strata:
        assert stratum.maximum_reference_recovery_count <= (
            stratum.structural_baseline_success_count
        )
        assert max(stratum.selector_success_counts.values()) <= (6 // stratum.choice_count)
    for package in _packages():
        for result in package.replica_results:
            for step in result.steps:
                state = step.prompt.state
                for values in state.argument_value_catalogs.values():
                    assert len(values) == len(state.choice_legend)
                    assert len({item.value_handle for item in values}) == len(values)
                lengths = {
                    len(
                        json.dumps(
                            resolve_encoded_operation(
                                state,
                                item.choice_handle,
                            ).model_dump(mode="json"),
                            sort_keys=True,
                            separators=(",", ":"),
                        ).encode()
                    )
                    for item in step.prompt.candidates
                }
                assert len(lengths) == 1


def test_family_specific_mechanism_semantics_restore_noncanonical_successes() -> None:
    audit = models.MechanismSemanticsAudit.model_validate(_load("mechanism_semantics_audit.json"))
    assert audit.legal_nonreference_execution_count == 146
    assert audit.wrong_current_rule_candidate_count == 20
    assert audit.wrong_current_rule_rejection_count == 20
    assert audit.accepted_nonreference_count == 126
    assert audit.base_valid_nonreference_count == 24
    assert audit.mechanism_qualified_nonreference_count == 32
    assert audit.qualified_valid_nonreference_count == 24
    assert audit.base_valid_mechanism_false_count == 0
    assert audit.context_noncanonical_base_and_mechanism_valid_count == 6
    assert audit.reconciliation_noncanonical_base_and_mechanism_valid_count == 4
    assert audit.same_rule_noncanonical_recovery_count == 20
    assert audit.same_rule_retry_success_count == 14
    assert audit.same_rule_base_valid_count == 14
    assert audit.same_rule_mechanism_qualified_count == 14
    assert audit.same_rule_qualified_valid_count == 14
    assert audit.exact_reference_selector_required_count == 0
    assert audit.reference_baseline_qualified_count == audit.reference_baseline_count == 192
    for package in _packages():
        for result in package.replica_results:
            assert result.mechanism_qualification.reference_path_match is True
            assert result.mechanism_qualification.mechanism_semantically_qualified is True
            assert result.qualified_validity.qualified_valid is True


def test_exact_failure_receipt_is_visible_before_prompt_and_consumed_by_retry() -> None:
    audit = models.ExactFailureReceiptAudit.model_validate(
        _load("exact_failure_receipt_audit.json")
    )
    assert audit.recovery_prompt_count == 120
    assert audit.real_failure_before_prompt_count == 120
    assert audit.prompt_receipt_complete_count == 120
    assert audit.prompt_runtime_receipt_identity_match_count == 120
    assert audit.failure_retry_receipt_identity_match_count == 120
    assert audit.rule_binding_match_count == 120
    assert audit.failed_selector_hash_match_count == 120
    assert audit.error_code_match_count == 120
    assert audit.source_tool_match_count == 120
    assert audit.missing_receipt_rejection_count == 20
    assert audit.changed_receipt_id_rejection_count == 20
    assert audit.changed_error_rejection_count == 20
    assert audit.changed_selector_hash_rejection_count == 20
    assert audit.changed_source_tool_rejection_count == 20
    assert audit.changed_rule_rejection_count == 20
    assert audit.retry_after_receipt_rejection_count == 0
    recovery_results = tuple(
        result
        for package in _packages()
        if package.capability_family.value == "failure_recovery"
        for result in package.replica_results
    )
    assert len(recovery_results) == 48
    assert sum(len(item.steps) for item in recovery_results) == 120
    for result in recovery_results:
        for step in result.steps:
            receipt = step.prompt.state.failure_receipt
            assert receipt is not None
            assert "actual_failure_receipt" not in step.prompt.state.facts
            failure = next(
                item for item in result.events if item.event_id == receipt.failure_event_id
            )
            retry = next(
                item
                for item in result.events
                if item.component_key == step.component_key
                and item.event_type == "recovery_succeeded"
            )
            assert failure.event_type == "typed_failure_observed"
            assert failure.event_index < retry.event_index
            assert step.failure_receipt_id == receipt.receipt_id
            assert step.acceptance.failure_receipt_id == receipt.receipt_id
            assert retry.public_effects["failure_receipt_id"] == receipt.receipt_id


def test_true_step_runtime_and_zero_prompt_runner_have_exact_denominators() -> None:
    audit = models.StepRuntimeAudit.model_validate(_load("step_runtime_audit.json"))
    runner = models.HardenedRunnerInputCatalog.model_validate(
        _load("hardened_runner_input_catalog.json")
    )
    catalog = _catalog()
    assert audit.replica_execution_count == audit.initialize_count == audit.finalize_count == 192
    assert audit.render_current_prompt_count == audit.step_count == 480
    assert audit.reached_observation_count == 480
    assert audit.actual_runtime_event_count == 1104
    assert audit.predecessor_conditioned_prompt_count == 288
    assert audit.bound_predecessor_receipt_link_count == 480
    assert audit.preprompt_failure_event_count == 120
    assert audit.retry_consuming_exact_receipt_count == 120
    assert audit.complete_baseline_result_load_count == 0
    assert audit.static_reference_trace_input_count == 0
    assert audit.reference_qualified_count == 192
    assert runner.package_count == 32
    assert len({item.package_id for item in runner.packages}) == 32
    assert len({item.source_package_artifact_id for item in runner.packages}) == 32
    assert len({item.source_package_id for item in runner.packages}) == 32
    assert {item.source_package_artifact_id for item in runner.packages} == {
        item.source_v171_package_artifact_id for group in catalog.groups for item in group.packages
    }
    assert runner.materialized_prompt_count == runner.materialized_observation_count == 0
    forbidden = {"prompts", "observations", "replica_results", "steps", "reference_traces"}
    assert not (set(models.HardenedRunnerInputPackage.model_fields) & forbidden)


def test_contract_parent_closure_and_all_production_mutations_fail_closed() -> None:
    parent = models.ParentClosureAudit.model_validate(_load("parent_closure_audit.json"))
    destructive = models.ProductionDestructiveAudit.model_validate(
        _load("production_destructive_audit.json")
    )
    assert parent.package_reconstruction_match_count == 32
    assert parent.package_identity_recomputation_match_count == 32
    assert parent.public_task_identity_match_count == 32
    assert parent.authoritative_contract_binding_match_count == 192
    assert parent.runner_unique_package_count == 32
    assert parent.runner_unique_source_artifact_count == 32
    assert parent.runner_unique_source_package_count == 32
    assert (
        parent.runner_missing_count
        == parent.runner_duplicate_count
        == parent.runner_extra_count
        == 0
    )
    assert parent.fully_rehashed_mutation_count == parent.fully_rehashed_rejection_count == 16
    assert parent.accepted_mutation_count == 0
    assert destructive.mutation_count == destructive.rejection_count == 31
    assert destructive.acceptance_count == 0
    names = {item.mutation for item in destructive.mutations}
    assert {
        "action_rank_candidate_position_joint_recovery",
        "display_rank_legend_position_joint_recovery",
        "fully_rehashed_development_public_task_id_changed",
        "fully_rehashed_runner_duplicate_drop",
        "fully_rehashed_runner_source_development_catalog_id_changed",
        "prompt_failure_receipt_deleted",
        "prompt_failure_receipt_identity_replaced",
        "prompt_failure_receipt_error_replaced",
        "wrong_current_rule_retry_attempt",
    } <= names


def test_empty_directory_rebuild_is_byte_identical_and_zero_call(tmp_path: Path) -> None:
    rebuilt = tmp_path / "v26_174_rebuilt"
    products = build_module.build(
        package_root=PACKAGE_ROOT,
        output_dir=rebuilt,
        external_audit_path=FORMAL_DIR / "external_joint_audit_input.txt",
    )
    assert products.report.provider_calls == 0
    assert products.report.development_jobs == 0
    expected = {item.name for item in FORMAL_DIR.iterdir() if item.is_file()}
    observed = {item.name for item in rebuilt.iterdir() if item.is_file()}
    assert observed == expected
    for name in sorted(expected):
        assert (rebuilt / name).read_bytes() == (FORMAL_DIR / name).read_bytes()
