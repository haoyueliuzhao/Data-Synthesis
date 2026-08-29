from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any

from trusted_synthesis.core.task.semantic_table_trace_hardening import (
    resolve_encoded_operation,
)
from trusted_synthesis.experiments.vtdo_experiment import (
    phase1_v26_capability_semantic_table_trace_hardening as build_module,
)
from trusted_synthesis.experiments.vtdo_experiment import (
    phase1_v26_capability_semantic_table_trace_hardening_models as models,
)

PACKAGE_ROOT = Path(__file__).resolve().parents[1]
FORMAL_DIR = Path(os.environ.get("V26_173_TEST_FORMAL_DIR", PACKAGE_ROOT / build_module.OUTPUT_DIR))


def _load(name: str) -> Any:
    return json.loads((FORMAL_DIR / name).read_text(encoding="utf-8"))


def _catalog() -> models.HardenedDevelopmentCatalog:
    return models.HardenedDevelopmentCatalog.model_validate(
        _load("hardened_development_catalog.json")
    )


def _packages() -> tuple[models.HardenedDevelopmentPackage, ...]:
    return tuple(item for group in _catalog().groups for item in group.packages)


def test_formal_v26_173_chain_consumes_only_the_zero_call_hardening_stage() -> None:
    report = models.HardeningReport.model_validate(_load("report.json"))
    authorization = models.ExternalAuditAuthorization.model_validate(
        _load("external_audit_authorization.json")
    )
    predecessor = models.PredecessorFreezeAudit.model_validate(
        _load("v172_predecessor_freeze_audit.json")
    )
    defect = models.V172DefectReproductionAudit.model_validate(
        _load("v172_defect_reproduction_audit.json")
    )
    static = models.StaticAudit.model_validate(_load("static_audit.json"))
    transition = models.ProspectiveTransition.model_validate(
        _load("prospective_transition_contract.json")
    )
    assert authorization.review_sha256 == build_module.EXPECTED_REVIEW_SHA256
    assert authorization.review_byte_count == build_module.EXPECTED_REVIEW_BYTE_COUNT
    assert predecessor.file_count == predecessor.independent_rebuild_match_count == 22
    assert defect.stable_index_rule_recovery_count == 240
    assert defect.decoded_operation_length_recovery_count == 192
    assert defect.recovery_contract_conflict_count == 6
    assert defect.accepted_fully_rehashed_parent_mutation_count == 4
    assert defect.external_reported_action_id_rank_imbalanced_state_count == 56
    assert defect.direct_recomputed_action_id_rank_imbalanced_state_count == 64
    assert static.passed_gate_count == static.gate_count == 15
    assert report.provider_calls == report.development_jobs == 0
    assert transition.blocked_predecessor_stage == (
        "capability_observation_dynamic_depth_development_runner_preflight_only"
    )
    assert transition.next_stage == models.NEXT_STAGE
    assert transition.provider_calls_authorized is False
    assert transition.development_jobs_authorized is False


def test_replica_local_tables_and_every_registered_stratum_stay_at_baseline() -> None:
    audit = models.StratifiedShortcutAudit.model_validate(_load("stratified_shortcut_audit.json"))
    assert audit.stratum_count == audit.target_state_count == 80
    assert audit.presentation_count == 480
    assert audit.displayed_candidate_count == 1356
    assert audit.excess_stratum_count == 0
    assert audit.stable_cross_replica_value_vector_count == 0
    assert audit.unique_encoded_operation_length_presentation_count == 0
    assert audit.action_id_rank_imbalance_count == 0
    assert audit.value_handle_rank_imbalance_count == 0
    assert audit.visible_padding_field_count == 0
    for stratum in audit.strata:
        assert max(stratum.selector_success_counts.values()) <= (
            stratum.structural_baseline_success_count
        )
    totals = {
        name: sum(item.selector_success_counts[name] for item in audit.strata)
        for name in audit.strata[0].selector_success_counts
    }
    assert totals == {
        "action_id_order": 174,
        "argument_field_order": 0,
        "candidate_position": 174,
        "catalog_lexical_order": 146,
        "choice_handle_order": 174,
        "encoded_operation_length": 0,
        "fixed_value_handle_vector": 0,
        "legend_position": 174,
        "maximum_value_handle_vector": 146,
        "minimum_value_handle_vector": 146,
    }
    for package in _packages():
        for result in package.replica_results:
            for step in result.steps:
                lengths = {
                    len(
                        json.dumps(
                            resolve_encoded_operation(
                                step.prompt.state,
                                item.choice_handle,
                            ).model_dump(mode="json"),
                            sort_keys=True,
                            separators=(",", ":"),
                        ).encode()
                    )
                    for item in step.prompt.candidates
                }
                assert len(lengths) == 1


def test_recovery_preconditions_are_hard_bound_to_mechanism_and_qualified_validity() -> None:
    audit = models.RecoveryStateConsistencyAudit.model_validate(
        _load("recovery_state_consistency_audit.json")
    )
    assert audit.wrong_current_rule_candidate_count == 20
    assert audit.state_precondition_invalid_count == 20
    assert audit.action_acceptance_count == 0
    assert audit.mechanism_semantically_qualified_count == 0
    assert audit.qualified_valid_count == 0
    assert audit.typed_target_mismatch_count == 20
    assert audit.retry_after_target_mismatch_count == 0
    assert audit.reference_recovery_execution_count == 20
    assert audit.reference_rule_receipt_lineage_pass_count == 20
    assert audit.reference_qualified_count == 20
    assert audit.row_level_parent_binding_count == 40
    recovery_results = tuple(
        result
        for package in _packages()
        if package.capability_family.value == "failure_recovery"
        for result in package.replica_results
    )
    assert len(recovery_results) == 48
    for result in recovery_results:
        assert result.qualified_validity.qualified_valid is True
        assert result.mechanism_qualification.all_state_preconditions_passed is True
        assert result.mechanism_qualification.recovery_rule_receipt_lineage_passed is True
        for step in result.steps:
            failures = tuple(
                item
                for item in result.events
                if item.component_key == step.component_key
                and item.event_type == "typed_failure_observed"
            )
            retries = tuple(
                item
                for item in result.events
                if item.component_key == step.component_key
                and item.event_type == "recovery_succeeded"
            )
            assert len(failures) == len(retries) == 1
            assert (
                failures[0].public_effects["rule_handle"]
                == retries[0].public_effects["rule_handle"]
            )
            assert (
                failures[0].public_effects["failure_receipt_id"]
                == retries[0].public_effects["failure_receipt_id"]
            )


def test_true_step_runtime_uses_only_reached_state_and_zero_prompt_runner_input() -> None:
    audit = models.StepRuntimeAudit.model_validate(_load("step_runtime_audit.json"))
    runner_input = models.HardenedRunnerInputCatalog.model_validate(
        _load("hardened_runner_input_catalog.json")
    )
    assert audit.replica_execution_count == audit.initialize_count == audit.finalize_count == 192
    assert audit.render_current_prompt_count == audit.step_count == 480
    assert audit.reached_observation_count == 480
    assert audit.actual_runtime_event_count == 1104
    assert audit.predecessor_conditioned_prompt_count == 288
    assert audit.bound_predecessor_receipt_link_count == 480
    assert audit.complete_baseline_result_load_count == 0
    assert audit.baseline_event_filter_count == 0
    assert audit.static_reference_trace_input_count == 0
    assert audit.reference_qualified_count == 192
    assert runner_input.package_count == 32
    assert runner_input.materialized_prompt_count == 0
    assert runner_input.materialized_observation_count == 0
    forbidden = {"prompts", "observations", "replica_results", "steps", "reference_traces"}
    assert not (set(models.HardenedRunnerInputPackage.model_fields) & forbidden)
    for package in _packages():
        for result in package.replica_results:
            receipts: dict[str, str] = {}
            assert result.complete_baseline_loaded is False
            assert result.precommitted_choice_vector_allowed is False
            assert result.future_prompt_access_allowed is False
            for step in result.steps:
                expected = tuple(receipts[key] for key in step.dependency_component_keys)
                assert step.observation.predecessor_receipt_ids == expected
                assert (
                    tuple(item.receipt_id for item in step.prompt.state.prior_observations)
                    == expected
                )
                assert set(step.observation.event_ids) <= {item.event_id for item in result.events}
                receipts[step.component_key] = step.observation.receipt_id


def test_exact_parent_reconstruction_and_future_estimand_boundaries_close() -> None:
    parent = models.SemanticParentReconstructionAudit.model_validate(
        _load("semantic_parent_reconstruction_audit.json")
    )
    estimand_contract = models.SequentialEstimandContract.model_validate(
        _load("sequential_estimand_contract.json")
    )
    estimand = models.SequentialEstimandAudit.model_validate(
        _load("sequential_estimand_registration_audit.json")
    )
    destructive = models.ProductionDestructiveAudit.model_validate(
        _load("production_destructive_audit.json")
    )
    assert parent.package_reconstruction_match_count == 32
    assert parent.prompt_reconstruction_match_count == 480
    assert parent.display_source_mapping_match_count == 480
    assert parent.reference_operation_match_count == 480
    assert parent.observation_effect_match_count == 480
    assert parent.receipt_parent_match_count == 480
    assert parent.mechanism_report_match_count == 192
    assert parent.runner_input_topology_match_count == 32
    assert parent.fully_rehashed_mutation_count == 4
    assert parent.fully_rehashed_rejection_count == 4
    assert parent.accepted_mutation_count == 0
    assert estimand_contract.empirical_value_count == 0
    assert estimand.empirical_row_count == 0
    assert estimand.latent_ability_boundary_count == 0
    assert destructive.mutation_count == destructive.rejection_count == 19
    assert destructive.acceptance_count == 0
    assert {
        "fully_rehashed_reference_path_changed",
        "fully_rehashed_mechanism_parent_changed",
        "fully_rehashed_display_mapping_changed",
        "fully_rehashed_runner_topology_reversed",
        "provider_authorization_enabled",
    }.issubset({item.mutation for item in destructive.mutations})


def test_empty_directory_rebuild_is_byte_identical_and_zero_call(tmp_path: Path) -> None:
    rebuilt = tmp_path / "v26_173_rebuilt"
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
