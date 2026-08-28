from __future__ import annotations

import hashlib
import json
import os
from collections import Counter
from pathlib import Path
from typing import Any

from trusted_synthesis.core.task.capability_observation import (
    OBSERVATION_DEPTH_ORDER,
    CapabilityFamily,
)
from trusted_synthesis.core.task.public_semantic_capability_depth import (
    candidate_grounding_findings,
    canonical_bytes,
    public_only_select_action,
    scan_model_visible_leakage,
)
from trusted_synthesis.experiments.vtdo_experiment import (
    phase1_v26_capability_public_semantic_execution_hardening as build_module,
)
from trusted_synthesis.experiments.vtdo_experiment import (
    phase1_v26_capability_public_semantic_execution_models as models,
)

PACKAGE_ROOT = Path(__file__).resolve().parents[1]
FORMAL_DIR = Path(os.environ.get("V26_170_TEST_FORMAL_DIR", PACKAGE_ROOT / build_module.OUTPUT_DIR))


def _load(name: str) -> Any:
    return json.loads((FORMAL_DIR / name).read_text(encoding="utf-8"))


def _catalog() -> models.HardenedSemanticDevelopmentCatalog:
    return models.HardenedSemanticDevelopmentCatalog.model_validate(
        _load("hardened_semantic_development_catalog.json")
    )


def _packages() -> tuple[models.HardenedSemanticPackage, ...]:
    return tuple(package for group in _catalog().groups for package in group.packages)


def test_formal_public_semantic_hardening_chain_closes_all_gates() -> None:
    report = models.PublicSemanticHardeningReport.model_validate(_load("report.json"))
    authorization = models.ExternalAuditAuthorization.model_validate(
        _load("external_audit_authorization.json")
    )
    predecessor = models.PredecessorIntegrityAudit.model_validate(
        _load("predecessor_integrity_audit.json")
    )
    defect = models.V169SemanticDefectAudit.model_validate(_load("v169_semantic_defect_audit.json"))
    sufficiency = models.PublicSemanticSufficiencyAudit.model_validate(
        _load("public_semantic_sufficiency_audit.json")
    )
    grounding = models.CandidateGroundingAudit.model_validate(
        _load("candidate_grounding_audit.json")
    )
    execution = models.RealProgramExecutionAudit.model_validate(
        _load("real_program_execution_audit.json")
    )
    isolation = models.TargetIsolationAudit.model_validate(_load("target_isolation_audit.json"))
    increments = models.DepthIncrementNecessityCatalog.model_validate(
        _load("depth_increment_necessity_catalog.json")
    )
    parent = models.PromptParentBindingAudit.model_validate(
        _load("prompt_parent_binding_audit.json")
    )
    replica = models.ReplicaPresentationAudit.model_validate(
        _load("replica_presentation_audit.json")
    )
    static = models.PublicSemanticStaticAudit.model_validate(
        _load("public_semantic_static_audit.json")
    )
    transition = models.PublicSemanticTransition.model_validate(
        _load("prospective_transition_contract.json")
    )

    assert report.status == "passed"
    assert report.finance_core_count == 8
    assert report.development_package_count == report.baseline_qualified_count == 32
    assert report.target_state_count == 80
    assert report.semantic_candidate_count == 240
    assert report.depth_increment_counterfactual_count == 48
    assert report.replica_presentation_count == 480
    assert report.provider_calls == report.stage_two_provider_calls == report.gpu_jobs == 0
    assert report.development_jobs == report.confirmation_payload_access_count == 0
    assert report.model_behavior_measured is report.runner_preflighted is False
    assert authorization.review_sha256 == build_module.EXPECTED_REVIEW_SHA256
    assert authorization.review_byte_count == build_module.EXPECTED_REVIEW_BYTE_COUNT
    assert predecessor.matched_file_count == len(predecessor.bindings) == 17
    assert predecessor.stale_runner_preflight_transition_blocked is True
    assert predecessor.sealed_confirmation_payload_loaded is False

    assert defect.original_public_instruction_exact_count == 0
    assert defect.registered_alias_value_retained_count == 0
    assert defect.registered_period_value_retained_count == 0
    assert defect.resolution_rule_value_retained_count == 0
    assert defect.resolution_rule_value_count == 101
    assert defect.unique_public_task_projection_hash_count == 5
    assert defect.reference_parameter_externally_bound_state_count == 8
    assert defect.no_candidate_parameter_externally_bound_state_count == 202
    assert defect.rehashed_public_task_parent_mutation_accepted is True

    assert sufficiency.exact_instruction_retained_count == 8
    assert sufficiency.alias_value_retained_count == 23
    assert sufficiency.period_value_retained_count == 14
    assert sufficiency.resolution_rule_value_retained_count == 101
    assert sufficiency.unique_public_task_hash_count == 8
    assert sufficiency.production_public_only_unique_choice_count == 80
    assert sufficiency.independent_public_only_unique_choice_count == 80
    assert sufficiency.replica_public_only_choice_match_count == 480
    assert sufficiency.action_id_or_ordinal_dependency_count == 0
    assert sufficiency.source_oracle_dependency_count == 0
    assert sufficiency.opaque_hash_guess_state_count == 0
    assert sufficiency.model_visible_host_leak_count == 0
    assert grounding.semantic_candidate_count == grounding.publicly_grounded_candidate_count == 240
    assert grounding.ungrounded_candidate_count == 0
    assert (
        grounding.indexed_shortcut_candidate_count
        == grounding.random_peer_hash_candidate_count
        == 0
    )

    assert execution.task_program_executor_invocation_count == 32
    assert execution.task_program_oracle_verifier_invocation_count == 32
    assert execution.baseline_program_valid_count == 32
    assert execution.baseline_base_valid_count == 32
    assert execution.baseline_mechanism_qualified_count == 32
    assert execution.baseline_qualified_valid_count == 32
    assert execution.predecessor_output_match_count == 32
    assert execution.host_result_assignment_count == 0
    assert isolation.target_choice_state_count == 80
    assert isolation.non_target_choice_state_count == 0
    assert increments.artifact_count == increments.task_invalid_count == 48
    assert parent.semantic_task_mutation_count == parent.reconstruction_rejection_count == 32
    assert parent.accepted_crossed_public_task_count == 0
    assert replica.presentation_count == 480
    assert replica.displayed_candidate_count == 1_440
    assert replica.per_state_position_imbalance_count == 0
    assert replica.action_id_collision_count == 0
    assert static.gate_count == static.passed_gate_count == len(static.gates) == 18
    assert transition.blocked_predecessor_stage == (
        "capability_observation_executable_depth_development_runner_preflight_only"
    )
    assert transition.next_stage == (
        "capability_observation_public_semantic_execution_development_runner_preflight_only"
    )
    assert transition.provider_calls_authorized is False
    assert transition.development_jobs_authorized is False
    assert transition.confirmation_payload_loading_authorized is False


def test_every_reference_is_constructible_from_current_public_semantics_only() -> None:
    generic_v169_instruction = (
        "Complete the currently visible finance operations and return the exact public result "
        "only after verification."
    )
    assert len({package.public_task.semantic_hash for package in _packages()}) == 8
    state_count = candidate_count = replica_count = 0
    for package in _packages():
        assert package.public_task.instruction != generic_v169_instruction
        assert len(package.public_task.records) == 2
        assert all(len(item.semantic_fields) >= 7 for item in package.public_task.records)
        assert "program_operator_id" not in package.public_task.model_dump(mode="json")
        assert "program_input_record_handles" not in package.public_task.model_dump(mode="json")
        prompts = {item.state.state_token: item for item in package.prompt_binding.prompts}
        for component in package.components:
            state_count += 1
            prompt = prompts[component.public_state.state_token]
            assert scan_model_visible_leakage(prompt.model_dump(mode="json")) == ()
            action_id = public_only_select_action(prompt)
            selected = next(item for item in prompt.candidates if item.action_id == action_id)
            reference = next(
                item
                for item in component.choices
                if item.semantic_key == component.reference_semantic_key
            )
            assert selected.operation == reference.operation
            assert len({len(canonical_bytes(item)) for item in prompt.candidates}) == 1
            for choice in component.choices:
                candidate_count += 1
                assert (
                    candidate_grounding_findings(
                        package.public_task,
                        component.public_state,
                        choice.operation,
                    )
                    == ()
                )
        components = {item.component_id: item for item in package.components}
        for presentation in package.replica_presentations:
            replica_count += 1
            action_id = public_only_select_action(presentation.prompt)
            selected = next(
                item for item in presentation.prompt.candidates if item.action_id == action_id
            )
            component = components[presentation.component_id]
            reference = next(
                item
                for item in component.choices
                if item.semantic_key == component.reference_semantic_key
            )
            assert selected.operation == reference.operation
    assert state_count == 80
    assert candidate_count == 240
    assert replica_count == 480


def test_real_program_execution_isolated_loads_and_increment_necessity_are_exact() -> None:
    catalog = _catalog()
    for group in catalog.groups:
        assert tuple(item.depth for item in group.packages) == OBSERVATION_DEPTH_ORDER
        assert tuple(item.target_load.total for item in group.packages) == (1, 2, 3, 4)
        assert all(item.target_load.non_target_choice_state_count == 0 for item in group.packages)
        component_sets = [
            set(item.component_key for item in package.components) for package in group.packages
        ]
        assert all(
            previous < current and len(current - previous) == 1
            for previous, current in zip(component_sets, component_sets[1:], strict=False)
        )
        for package in group.packages:
            result = package.baseline_execution
            assert result.selected_program is not None
            assert result.program_execution is not None
            assert result.oracle_verification is not None
            assert result.executor_invocation_count == result.oracle_verifier_invocation_count == 1
            assert result.program_valid is result.base_valid is True
            assert result.mechanism_qualified is result.qualified_valid is True
            assert result.result_assigned_by_host is False

    d0 = {group.capability_family: group.packages[0].target_load.total for group in catalog.groups}
    assert d0 == {family: 1 for family in CapabilityFamily}
    increments = models.DepthIncrementNecessityCatalog.model_validate(
        _load("depth_increment_necessity_catalog.json")
    )
    assert len(increments.artifacts) == 48
    assert all(not item.runtime_result.base_valid for item in increments.artifacts)
    assert all(not item.runtime_result.mechanism_qualified for item in increments.artifacts)
    assert all(not item.runtime_result.qualified_valid for item in increments.artifacts)
    assert all(
        item.runtime_result.result_assigned_by_host is False for item in increments.artifacts
    )


def test_six_replica_presentation_is_balanced_and_parent_rehash_is_rejected() -> None:
    action_ids: list[str] = []
    for package in _packages():
        for component in package.components:
            rows = tuple(
                item
                for item in package.replica_presentations
                if item.component_id == component.component_id
            )
            assert len(rows) == 6
            positions: dict[str, Counter[int]] = {
                item.semantic_key: Counter() for item in component.choices
            }
            for row in rows:
                for candidate in row.prompt.candidates:
                    positions[candidate.operation.semantic_key][candidate.presentation_index] += 1
                    action_ids.append(candidate.action_id)
            assert all(value == Counter({0: 2, 1: 2, 2: 2}) for value in positions.values())
    assert len(action_ids) == len(set(action_ids)) == 1_440

    parent = models.PromptParentBindingAudit.model_validate(
        _load("prompt_parent_binding_audit.json")
    )
    assert parent.semantic_task_mutation_count == 32
    assert parent.child_identity_recomputed_count == 32
    assert parent.package_identity_recomputed_count == 32
    assert parent.group_identity_recomputed_count == 32
    assert parent.catalog_identity_recomputed_count == 32
    assert parent.reconstruction_rejection_count == 32
    assert parent.accepted_crossed_public_task_count == 0


def test_empty_directory_rebuild_is_byte_identical_and_zero_call(tmp_path: Path) -> None:
    rebuilt = tmp_path / "formal"
    products = build_module.build(
        package_root=PACKAGE_ROOT,
        output_dir=rebuilt,
        external_audit_path=FORMAL_DIR / "external_joint_audit_input.txt",
    )
    assert products.report.provider_calls == products.report.stage_two_provider_calls == 0
    assert products.report.development_jobs == products.report.gpu_jobs == 0
    formal_names = {path.name for path in FORMAL_DIR.iterdir() if path.is_file()}
    rebuilt_names = {path.name for path in rebuilt.iterdir() if path.is_file()}
    assert rebuilt_names == formal_names
    for name in sorted(formal_names):
        assert (rebuilt / name).read_bytes() == (FORMAL_DIR / name).read_bytes()

    report = models.PublicSemanticHardeningReport.model_validate(_load("report.json"))
    detail_by_name = {item.relative_path: item for item in report.detail_files}
    assert set(detail_by_name) == formal_names - {"report.json"}
    for name, binding in detail_by_name.items():
        payload = (FORMAL_DIR / name).read_bytes()
        assert binding.byte_count == len(payload)
        assert binding.sha256 == hashlib.sha256(payload).hexdigest()
