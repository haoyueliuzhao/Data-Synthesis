from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any

from trusted_synthesis.core.task.capability_observation import CapabilityFamily
from trusted_synthesis.core.task.validity_separated_capability_depth import (
    candidate_legality_findings,
    public_only_select_action,
    public_prompt_shortcut_findings,
)
from trusted_synthesis.experiments.vtdo_experiment import (
    phase1_v26_capability_executable_depth_rematerialization_models as v168_models,
)
from trusted_synthesis.experiments.vtdo_experiment import (
    phase1_v26_capability_public_semantic_execution_models as v170_models,
)
from trusted_synthesis.experiments.vtdo_experiment import (
    phase1_v26_capability_validity_causal_reaudit as build_module,
)
from trusted_synthesis.experiments.vtdo_experiment import (
    phase1_v26_capability_validity_causal_reaudit_models as models,
)
from trusted_synthesis.experiments.vtdo_experiment import (
    phase1_v26_capability_validity_causal_reaudit_static_audit as static_audit,
)

PACKAGE_ROOT = Path(__file__).resolve().parents[1]
FORMAL_DIR = Path(os.environ.get("V26_171_TEST_FORMAL_DIR", PACKAGE_ROOT / build_module.OUTPUT_DIR))


def _load(name: str) -> Any:
    return json.loads((FORMAL_DIR / name).read_text(encoding="utf-8"))


def _catalog() -> models.ValiditySeparatedDevelopmentCatalog:
    return models.ValiditySeparatedDevelopmentCatalog.model_validate(
        _load("validity_separated_development_catalog.json")
    )


def _packages() -> tuple[models.ValiditySeparatedCausalPackage, ...]:
    return tuple(package for group in _catalog().groups for package in group.packages)


def test_formal_v26_171_chain_closes_exact_authorized_static_stage() -> None:
    report = models.ValidityCausalReauditReport.model_validate(_load("report.json"))
    authorization = models.ExternalAuditAuthorization.model_validate(
        _load("external_audit_authorization.json")
    )
    predecessor = models.PredecessorIntegrityAudit.model_validate(
        _load("predecessor_integrity_audit.json")
    )
    defect = models.V170DefectReproductionAudit.model_validate(
        _load("v170_defect_reproduction_audit.json")
    )
    static = models.ValidityCausalStaticAudit.model_validate(
        _load("validity_causal_static_audit.json")
    )
    transition = models.ValidityCausalTransition.model_validate(
        _load("prospective_transition_contract.json")
    )
    assert report.authorization_id == authorization.authorization_id
    assert report.predecessor_integrity_audit_id == predecessor.audit_id
    assert report.defect_reproduction_audit_id == defect.audit_id
    assert report.static_audit_id == static.audit_id
    assert report.transition_id == transition.transition_id
    assert static.passed_gate_count == static.gate_count == 15
    assert predecessor.stale_runner_preflight_transition_blocked is True
    assert defect.nonreference_program_valid_count == 100
    assert defect.depth_increment_program_valid_count == 28
    assert defect.unique_reference_padding_length_state_count == 34
    assert transition.provider_calls_authorized is False
    assert transition.development_jobs_authorized is False
    assert transition.next_stage == (
        "capability_observation_validity_separated_causal_deleaked_"
        "development_runner_preflight_only"
    )


def test_base_and_mechanism_are_independent_and_public_answers_are_complete() -> None:
    validity = models.ValiditySeparationAudit.model_validate(
        _load("validity_separation_audit.json")
    )
    answers = models.PublicAnswerProjectionAudit.model_validate(
        _load("public_answer_projection_audit.json")
    )
    increments = models.DepthIncrementCausalCatalog.model_validate(
        _load("depth_increment_causal_catalog.json")
    )
    assert validity.baseline_base_valid_count == 32
    assert validity.baseline_mechanism_qualified_count == 32
    assert validity.nonreference_counterfactual_count == 146
    assert validity.base_true_mechanism_false_count == 26
    assert validity.base_false_mechanism_false_count == 120
    assert validity.base_true_mechanism_true_count == 0
    assert validity.base_reference_metadata_input_count == 0
    assert answers.raw_internal_reference_package_count == 24
    assert answers.public_reference_projection_complete_count == 24
    assert answers.exact_answer_schema_pass_count == 32
    assert answers.canonical_semantic_match_count == 32
    assert increments.artifact_count == 44
    assert increments.task_level_necessary_count == 38
    assert increments.mechanism_necessary_count == 44
    assert increments.base_true_mechanism_false_count == 6
    assert all(
        item.counterfactual_result_id == item.counterfactual_result.result_id
        for item in increments.artifacts
    )


def test_every_component_has_a_real_family_specific_causal_consequence() -> None:
    catalog = _catalog()
    causal = models.CausalComponentAudit.model_validate(_load("causal_component_audit.json"))
    family = models.ComponentFamilyAudit.model_validate(_load("component_family_audit.json"))
    assert causal.target_component_count == causal.component_causal_effect_count == 80
    assert causal.real_task_program_executor_call_count == 32
    assert causal.real_task_program_verifier_call_count == 32
    assert causal.normalization_runtime_call_count == 16
    assert causal.normalized_reference_emitted_count == 16
    assert causal.normalized_reference_consumed_count == 16
    assert causal.typed_failure_observation_count == 20
    assert causal.successful_recovery_count == 20
    assert causal.dynamic_readiness_receipt_count == 8
    assert causal.postcompletion_control_count == 16
    assert causal.synthetic_set_result_effect_count == 0
    assert causal.wrong_readiness_changes_terminal_count > 0
    assert family.family_validator_pass_count == 80
    assert family.reconciliation_operator_target_count == 0
    for package in _packages():
        result = package.baseline_execution
        assert result.qualified_validity.qualified_valid is True
        assert result.task_validity.report_id != result.mechanism_qualification.report_id
        assert result.task_program_oracle_verifier_invocation_count == 1
        assert all(result.mechanism_qualification.component_checks.values())
        assert all(result.mechanism_qualification.component_event_ids.values())
        if package.capability_family == CapabilityFamily.SEMANTIC_RECONCILIATION:
            event_types = {item.event_type for item in result.events}
            assert "normalization_reference_emitted" in event_types
            assert "normalization_reference_consumed" in event_types
            assert "reconciliation.terminal_calculator" in event_types
    assert catalog.provider_calls == 0


def test_deleaked_presentations_are_public_only_balanced_and_runtime_legal() -> None:
    presentation = models.PresentationDeleakAudit.model_validate(
        _load("presentation_deleak_audit.json")
    )
    legality = models.CandidateLegalityAudit.model_validate(_load("candidate_legality_audit.json"))
    assert presentation.presentation_count == 480
    assert presentation.displayed_candidate_count == 1356
    assert presentation.visible_padding_field_count == 0
    assert presentation.padding_only_unique_selector_count == 0
    assert presentation.candidate_byte_length_unique_selector_count == 0
    assert presentation.argument_count_unique_selector_count == 0
    assert presentation.field_count_unique_selector_count == 0
    assert presentation.per_state_position_imbalance_count == 0
    assert legality.semantic_candidate_count == legality.runtime_legal_candidate_count == 226
    assert legality.illegal_operator_candidate_count == 0
    for package in _packages():
        components = {item.component_id: item for item in package.components}
        for row in package.replica_presentations:
            component = components[row.component_id]
            assert public_prompt_shortcut_findings(row.prompt) == ()
            action_id = public_only_select_action(row.prompt)
            selected = next(
                item.choice_handle for item in row.prompt.candidates if item.action_id == action_id
            )
            assert selected == component.reference_choice_handle
            for entry in component.public_state.choice_legend:
                assert (
                    candidate_legality_findings(
                        package.public_task,
                        component.public_state,
                        entry.operation,
                    )
                    == ()
                )


def test_all_semantic_parents_reconstruct_and_destructive_mutations_fail_closed() -> None:
    catalog = _catalog()
    validity = models.ValiditySeparationContract.model_validate(
        _load("validity_separation_contract.json")
    )
    component = models.CausalComponentContract.model_validate(
        _load("causal_component_contract.json")
    )
    presentation = models.DeleakedPresentationPolicy.model_validate(
        _load("deleaked_presentation_policy.json")
    )
    parent = models.SemanticParentBindingContract.model_validate(
        _load("semantic_parent_binding_contract.json")
    )
    source_catalog = v170_models.HardenedSemanticDevelopmentCatalog.model_validate(
        json.loads(
            (
                PACKAGE_ROOT / build_module.V170_DIR / "hardened_semantic_development_catalog.json"
            ).read_text(encoding="utf-8")
        )
    )
    v168_catalog = v168_models.ExecutableDepthCatalog.model_validate(
        json.loads(
            (
                PACKAGE_ROOT / build_module.V168_DIR / "development_executable_depth_catalog.json"
            ).read_text(encoding="utf-8")
        )
    )
    static_audit.validate_catalog_reconstruction(
        catalog=catalog,
        source_catalog=source_catalog,
        v168_catalog=v168_catalog,
        validity=validity,
        component_contract=component,
        presentation_policy=presentation,
        parent_contract=parent,
    )
    binding = models.SemanticParentBindingAudit.model_validate(
        _load("semantic_parent_binding_audit.json")
    )
    destructive = models.ProductionDestructiveAudit.model_validate(
        _load("production_destructive_audit.json")
    )
    assert binding.reference_recomputation_match_count == 80
    assert binding.source_program_verification_recomputation_match_count == 32
    assert binding.depth_increment_parent_match_count == 44
    assert binding.whole_graph_rehash_rejection_count == 6
    assert binding.crossed_parent_acceptance_count == 0
    assert destructive.mutation_count == destructive.rejected_count == 17
    assert destructive.accepted_count == 0
    assert {
        "padding_only_selector",
        "candidate_byte_length_selector",
        "argument_count_only_selector",
        "field_count_only_selector",
    }.issubset({item.mutation for item in destructive.mutations})


def test_empty_directory_rebuild_is_byte_identical_and_zero_call(tmp_path: Path) -> None:
    rebuilt = tmp_path / "v26_171_rebuilt"
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
