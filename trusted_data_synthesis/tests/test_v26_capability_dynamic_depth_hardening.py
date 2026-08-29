from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any

from trusted_synthesis.core.task.dynamic_capability_depth import (
    public_only_select_dynamic_action,
    resolve_dynamic_operation,
)
from trusted_synthesis.experiments.vtdo_experiment import (
    phase1_v26_capability_dynamic_depth_hardening as build_module,
)
from trusted_synthesis.experiments.vtdo_experiment import (
    phase1_v26_capability_dynamic_depth_hardening_models as models,
)

PACKAGE_ROOT = Path(__file__).resolve().parents[1]
FORMAL_DIR = Path(os.environ.get("V26_172_TEST_FORMAL_DIR", PACKAGE_ROOT / build_module.OUTPUT_DIR))


def _load(name: str) -> Any:
    return json.loads((FORMAL_DIR / name).read_text(encoding="utf-8"))


def _catalog() -> models.DynamicHardeningCatalog:
    return models.DynamicHardeningCatalog.model_validate(
        _load("dynamic_depth_development_catalog.json")
    )


def _packages() -> tuple[models.DynamicHardeningPackage, ...]:
    return tuple(package for group in _catalog().groups for package in group.packages)


def test_formal_v26_172_chain_closes_only_the_zero_call_hardening_stage() -> None:
    report = models.DynamicHardeningReport.model_validate(_load("report.json"))
    authorization = models.ExternalAuditAuthorization.model_validate(
        _load("external_audit_authorization.json")
    )
    predecessor = models.PredecessorFreezeAudit.model_validate(
        _load("v171_predecessor_freeze_audit.json")
    )
    defect = models.V171DefectReproductionAudit.model_validate(
        _load("v171_defect_reproduction_audit.json")
    )
    static = models.DynamicHardeningStaticAudit.model_validate(
        _load("dynamic_depth_static_audit.json")
    )
    transition = models.DynamicHardeningTransition.model_validate(
        _load("prospective_transition_contract.json")
    )
    assert report.authorization_id == authorization.authorization_id
    assert report.predecessor_audit_id == predecessor.audit_id
    assert report.defect_audit_id == defect.audit_id
    assert report.static_audit_id == static.audit_id
    assert report.transition_id == transition.transition_id
    assert predecessor.file_count == predecessor.independent_rebuild_match_count == 23
    assert defect.reference_first_legend_state_count == 80
    assert defect.legend_first_reference_recovery_count == 480
    assert defect.reverse_topological_stopping_link_count == 12
    assert static.passed_gate_count == static.gate_count == 12
    assert report.provider_calls == report.development_jobs == 0
    assert transition.provider_calls_authorized is False
    assert transition.development_jobs_authorized is False
    assert transition.next_stage == (
        "capability_observation_dynamic_depth_development_runner_preflight_only"
    )


def test_legend_and_candidate_presentations_are_jointly_balanced_and_runner_input_is_empty() -> (
    None
):
    legend = models.LegendShortcutAudit.model_validate(_load("legend_shortcut_audit.json"))
    runner_input = models.DynamicRunnerInputCatalog.model_validate(
        _load("dynamic_runner_input_catalog.json")
    )
    assert legend.presentation_count == 480
    assert legend.displayed_candidate_count == 1356
    assert legend.unequal_legend_row_width_count == 0
    assert legend.legend_position_imbalance_count == 0
    assert legend.candidate_position_imbalance_count == 0
    assert legend.display_handle_rank_imbalance_count == 0
    assert legend.visible_padding_field_count == 0
    assert legend.stable_full_recovery_selector_count == 0
    assert max(legend.shortcut_success_counts.values()) == 174
    assert runner_input.package_count == 32
    assert runner_input.materialized_prompt_count == 0
    assert runner_input.materialized_observation_count == 0
    assert all(item.reference_trace_payload_accessible is False for item in runner_input.packages)
    assert all(item.precommitted_choice_vector_allowed is False for item in runner_input.packages)
    forbidden = {"baseline_prompts", "future_prompts", "replica_traces", "steps"}
    assert not (set(models.DynamicRunnerInputPackage.model_fields) & forbidden)


def test_reference_path_is_diagnostic_and_semantic_mechanism_is_broad() -> None:
    mechanism = models.MechanismSemanticsAudit.model_validate(
        _load("mechanism_semantics_audit.json")
    )
    legality = models.CandidateLegalityCatalog.model_validate(
        _load("candidate_legality_catalog.json")
    )
    assert mechanism.execution_count == 178
    assert mechanism.baseline_count == 32
    assert mechanism.legal_nonreference_count == 146
    assert mechanism.reference_path_match_count == 32
    assert mechanism.semantic_mechanism_qualified_count == 66
    assert mechanism.base_true_old_canonical_false_count == 26
    assert mechanism.base_true_old_canonical_false_semantic_true_count == 26
    assert mechanism.context_recovered_semantic_count == 6
    assert mechanism.recovery_recovered_semantic_count == 20
    assert mechanism.base_semantic_matrix == {
        "base_false_semantic_false": 112,
        "base_false_semantic_true": 8,
        "base_true_semantic_false": 0,
        "base_true_semantic_true": 58,
    }
    assert legality.candidate_count == 226
    assert legality.publicly_grounded_count == 226
    assert legality.publicly_executable_count == 226
    assert legality.state_precondition_valid_count == 206
    assert legality.mechanism_relevant_count == 206
    assert legality.task_semantically_valid_count == 106
    assert legality.recovery_wrong_current_rule_executable_count == 20
    assert legality.recovery_wrong_current_rule_state_valid_count == 0


def test_dynamic_traces_bind_reached_observations_and_topological_next_prompts() -> None:
    dynamic = models.DynamicDepthAudit.model_validate(_load("dynamic_depth_interaction_audit.json"))
    assert dynamic.replica_trace_count == 192
    assert dynamic.reached_prompt_count == dynamic.reached_observation_count == 480
    assert dynamic.declared_dependency_link_count == 80
    assert dynamic.predecessor_conditioned_prompt_count == 288
    assert dynamic.bound_predecessor_receipt_link_count == 480
    assert dynamic.reverse_topological_link_count == 0
    assert dynamic.complete_prompt_tuple_field_count == 0
    assert dynamic.precommitted_vector_rejection_count == 1
    assert dynamic.future_prompt_access_rejection_count == 1
    for package in _packages():
        for trace in package.replica_traces:
            receipt_by_key: dict[str, str] = {}
            for step in trace.steps:
                expected = tuple(receipt_by_key[key] for key in step.dependency_component_keys)
                assert step.observation.predecessor_receipt_ids == expected
                assert (
                    tuple(item.receipt_id for item in step.prompt.state.prior_observations)
                    == expected
                )
                action_id = public_only_select_dynamic_action(step.prompt)
                assert action_id == step.selected_action_id
                selected = next(
                    item for item in step.prompt.candidates if item.action_id == action_id
                )
                operation = resolve_dynamic_operation(
                    step.prompt.state,
                    selected.choice_handle,
                )
                assert operation.model_dump(mode="json") == step.observation.public_effects[
                    "selected_operation"
                ]
                receipt_by_key[step.component_key] = step.observation.receipt_id


def test_baseline_trace_parent_replay_and_destructive_controls_fail_closed() -> None:
    trace = models.BaselineTraceParentAudit.model_validate(
        _load("baseline_trace_parent_audit.json")
    )
    destructive = models.DynamicHardeningDestructiveAudit.model_validate(
        _load("production_destructive_audit.json")
    )
    assert trace.package_count == 32
    assert trace.canonical_result_match_count == 32
    assert trace.chosen_handle_match_count == 32
    assert trace.event_id_match_count == 32
    assert trace.event_order_match_count == 32
    assert trace.task_report_match_count == 32
    assert trace.mechanism_report_match_count == 32
    assert trace.qualified_report_match_count == 32
    assert trace.fully_rehashed_trace_mutation_count == 2
    assert trace.fully_rehashed_trace_rejection_count == 2
    assert trace.accepted_mutation_count == 0
    assert destructive.mutation_count == destructive.rejection_count == 14
    assert destructive.acceptance_count == 0
    assert {
        "fully_rehashed_selected_handles_changed",
        "fully_rehashed_event_order_changed",
        "precommitted_choice_vector_submitted",
        "model_visible_reference_fact_added",
        "provider_authorization_enabled",
    }.issubset({item.mutation for item in destructive.mutations})


def test_empty_directory_rebuild_is_byte_identical_and_zero_call(tmp_path: Path) -> None:
    rebuilt = tmp_path / "v26_172_rebuilt"
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
