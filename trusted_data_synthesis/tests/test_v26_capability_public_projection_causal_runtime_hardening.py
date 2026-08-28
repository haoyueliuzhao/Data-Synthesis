from __future__ import annotations

import hashlib
import json
import os
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any

import pytest

from trusted_synthesis.core.task.capability_observation import (
    OBSERVATION_DEPTH_ORDER,
    CapabilityFamily,
)
from trusted_synthesis.core.task.causal_capability_depth import (
    PUBLIC_ACTION_ID_LENGTH,
    CausalCapabilityDepthRuntime,
    CausalCounterfactualKind,
    CausalTerminalKind,
    FinanceEffect,
    FinanceEffectKind,
    apply_effects,
    canonical_bytes,
    initial_snapshot,
    scan_public_leakage,
)
from trusted_synthesis.experiments.vtdo_experiment import (
    phase1_v26_capability_public_projection_causal_runtime_hardening as build_module,
)
from trusted_synthesis.experiments.vtdo_experiment import (
    phase1_v26_capability_public_projection_causal_runtime_models as models,
)

PACKAGE_ROOT = Path(__file__).resolve().parents[1]
FORMAL_DIR = Path(os.environ.get("V26_169_TEST_FORMAL_DIR", PACKAGE_ROOT / build_module.OUTPUT_DIR))


def _load(name: str) -> Any:
    return json.loads((FORMAL_DIR / name).read_text(encoding="utf-8"))


def _catalog() -> models.CausalDevelopmentCatalog:
    return models.CausalDevelopmentCatalog.model_validate(_load("causal_development_catalog.json"))


def _packages() -> tuple[models.CausalDepthPackage, ...]:
    return tuple(package for group in _catalog().groups for package in group.packages)


def test_formal_causal_depth_hardening_chain_closes_every_authorized_gate() -> None:
    report = models.CausalDepthHardeningReport.model_validate(_load("report.json"))
    authorization = models.ExternalAuditAuthorization.model_validate(
        _load("external_audit_authorization.json")
    )
    predecessor = models.PredecessorIntegrityAudit.model_validate(
        _load("predecessor_integrity_audit.json")
    )
    defect = models.V168DefectReproductionAudit.model_validate(
        _load("v168_defect_reproduction_audit.json")
    )
    leakage = models.PublicProjectionLeakageAudit.model_validate(
        _load("public_projection_leakage_audit.json")
    )
    runtime = models.CausalRuntimeAudit.model_validate(_load("causal_runtime_audit.json"))
    parent = models.ParentBindingAudit.model_validate(_load("parent_binding_audit.json"))
    static = models.CausalDepthStaticAudit.model_validate(_load("causal_depth_static_audit.json"))
    transition = models.CausalDepthTransition.model_validate(
        _load("prospective_transition_contract.json")
    )

    assert report.status == "passed"
    assert report.development_package_count == report.baseline_qualified_count == 32
    assert report.task_level_counterfactual_count == 64
    assert report.provider_calls == report.stage_two_provider_calls == 0
    assert report.development_jobs == report.confirmation_payload_access_count == 0
    assert report.gpu_jobs == 0
    assert report.model_behavior_measured is report.runner_preflighted is False
    assert authorization.review_sha256 == build_module.EXPECTED_REVIEW_SHA256
    assert authorization.review_byte_count == build_module.EXPECTED_REVIEW_BYTE_COUNT
    assert authorization.confirmation_payload_access_count == 0
    assert predecessor.matched_file_count == len(predecessor.bindings) == 19
    assert predecessor.predecessor_mutation_count == 0
    assert predecessor.sealed_confirmation_payload_loaded is False
    assert predecessor.old_runner_preflight_transition_blocked is True
    assert defect.nonterminal_state_count == defect.all_candidates_same_successor_count == 142
    assert defect.reference_candidate_field_count == 142
    assert defect.target_capability_action_true_count == 244
    assert defect.v26_168_artifacts_rewritten is False
    assert leakage.prompt_projection_count == runtime.nonterminal_state_count == 210
    assert leakage.public_candidate_count == 630
    assert runtime.branch_divergent_state_count == 210
    assert runtime.all_candidates_same_successor_count == 0
    assert runtime.baseline_task_valid_count == 32
    assert runtime.baseline_mechanism_qualified_count == 32
    assert runtime.baseline_qualified_valid_count == 32
    assert parent.crossed_parent_mutation_count == parent.crossed_parent_rejection_count == 320
    assert parent.child_identity_recomputed_count == parent.package_identity_recomputed_count == 320
    assert parent.group_identity_recomputed_count == parent.catalog_identity_recomputed_count == 320
    assert len(static.gates) == static.gate_count == static.passed_gate_count == 22
    assert transition.next_stage == (
        "capability_observation_executable_depth_development_runner_preflight_only"
    )
    assert transition.provider_calls_authorized is False
    assert transition.development_jobs_authorized is False
    assert transition.confirmation_payload_loading_authorized is False
    assert transition.source_or_graph_change_authorized is False


def test_public_projection_is_current_state_only_opaque_and_recursively_leak_free() -> None:
    _catalog()
    projection_contract = json.dumps(
        _load("depth_prompt_projection_contract.json"), sort_keys=True
    ).casefold()
    assert '"future_graph_model_visible": false' in projection_contract
    assert '"reference_path_model_visible": false' in projection_contract
    assert '"required_events_model_visible": false' in projection_contract

    position_cells: dict[tuple[str, str, str], Counter[int]] = defaultdict(Counter)
    prompt_count = 0
    candidate_count = 0
    for package in _packages():
        graph = package.graph
        candidate_by_id = {item.candidate_id: item for item in graph.candidates}
        state_by_id = {item.state_id: item for item in graph.states}
        projections = {item.host_state_id: item for item in package.prompt_binding.projections}
        assert set(projections) == {
            item.state_id for item in graph.states if item.terminal_kind == CausalTerminalKind.NONE
        }
        for state_id, projection in projections.items():
            state = state_by_id[state_id]
            payload = projection.semantic_payload
            prompt_count += 1
            candidate_count += len(state.public_state.options)
            assert tuple(sorted(payload)) == ("state", "task")
            assert scan_public_leakage(payload) == ()
            assert projection.recursive_leakage_findings == ()
            assert projection.current_state_count == 1
            assert projection.future_state_count == 0
            encoded = json.dumps(payload, sort_keys=True).casefold()
            assert "reference_candidate_id" not in encoded
            assert "reference_action" not in encoded
            assert "target_capability_action" not in encoded
            assert "required_event_multiplicities" not in encoded
            assert package.capability_family.value not in encoded
            assert package.depth.value not in encoded
            assert graph.graph_id not in encoded
            lengths = {
                len(canonical_bytes(item.model_dump(mode="json")))
                for item in state.public_state.options
            }
            assert len(lengths) == 1
            assert all(
                len(item.action_id) == PUBLIC_ACTION_ID_LENGTH
                for item in state.public_state.options
            )
            assert len({item.action_id for item in state.public_state.options}) == 3
            reference = candidate_by_id[state.reference_candidate_id]
            option = next(
                item
                for item in state.public_state.options
                if item.action_id == reference.public_action_id
            )
            position_cells[
                (
                    package.capability_family.value,
                    package.depth.value,
                    state.host_phase,
                )
            ][option.presentation_index] += 1
    assert prompt_count == 210
    assert candidate_count == 630
    assert all(
        max(counter.get(index, 0) for index in range(3))
        - min(counter.get(index, 0) for index in range(3))
        <= 1
        for counter in position_cells.values()
    )


def test_runtime_has_real_branch_consequences_and_enforces_family_preconditions() -> None:
    packages = _packages()
    for package in packages:
        transitions = {item.candidate_id: item for item in package.graph.transitions}
        for state in package.graph.states:
            if state.terminal_kind == CausalTerminalKind.NONE:
                assert len(state.candidate_ids) == 3
                assert len({transitions[item].to_state_id for item in state.candidate_ids}) == 3
        assert package.baseline_witness.task_validity.base_valid is True
        assert package.baseline_witness.mechanism_validity.mechanism_qualified is True
        assert package.baseline_witness.qualified_validity.qualified_valid is True
        assert package.baseline_witness.task_validity.operation_lineage_complete is True
        runtime = CausalCapabilityDepthRuntime(package.graph, package.finance_binding)
        candidate_by_id = {item.candidate_id: item for item in package.graph.candidates}
        intervened = False
        for reference_id in package.graph.reference_path_candidate_ids:
            state = runtime.state
            alternatives = tuple(
                candidate_by_id[item]
                for item in state.candidate_ids
                if item != reference_id and candidate_by_id[item].target_capability_action
            )
            if alternatives:
                runtime.execute(alternatives[0].public_action_id)
                intervened = True
                break
            runtime.execute(candidate_by_id[reference_id].public_action_id)
        assert intervened is True
        assert runtime.state.terminal_kind != CausalTerminalKind.SUCCESS

    by_family = {
        family: next(item for item in packages if item.capability_family == family)
        for family in CapabilityFamily
    }
    reconciliation = by_family[CapabilityFamily.SEMANTIC_RECONCILIATION]
    with pytest.raises(ValueError, match="unproduced reference"):
        apply_effects(
            initial_snapshot(),
            (
                FinanceEffect(
                    kind=FinanceEffectKind.CONSUME_REFERENCE,
                    value=reconciliation.finance_binding.normalization_reference_ids[0],
                ),
            ),
            reconciliation.finance_binding,
        )
    recovery = by_family[CapabilityFamily.FAILURE_RECOVERY]
    selectors = recovery.finance_binding.selector_ids
    first_failure = recovery.finance_binding.selector_failure_codes[selectors[0]]
    mismatched = apply_effects(
        initial_snapshot(),
        (FinanceEffect(kind=FinanceEffectKind.RECORD_FAILURE, value=first_failure),),
        recovery.finance_binding,
    )
    with pytest.raises(ValueError, match="matching typed failure"):
        apply_effects(
            mismatched,
            (FinanceEffect(kind=FinanceEffectKind.REVISE_SELECTOR, value=selectors[1]),),
            recovery.finance_binding,
        )
    stopping = by_family[CapabilityFamily.STATE_DEPENDENT_STOPPING]
    with pytest.raises(ValueError, match="stopped before"):
        apply_effects(
            initial_snapshot(),
            (FinanceEffect(kind=FinanceEffectKind.STOP),),
            stopping.finance_binding,
        )
    assert all(
        any(
            state.terminal_kind == CausalTerminalKind.POSTCOMPLETION_VIOLATION
            for state in package.graph.states
        )
        for package in packages
        if package.capability_family == CapabilityFamily.STATE_DEPENDENT_STOPPING
    )


def test_depth_loads_counterfactuals_and_witness_claims_are_exactly_scoped() -> None:
    expected_loads = {
        CapabilityFamily.CONTEXT_CONDITIONED_ACTION: (29, 37, 45, 53),
        CapabilityFamily.SEMANTIC_RECONCILIATION: (50, 57, 65, 73),
        CapabilityFamily.FAILURE_RECOVERY: (37, 45, 53, 69),
        CapabilityFamily.STATE_DEPENDENT_STOPPING: (36, 43, 50, 57),
    }
    catalog = _catalog()
    for group in catalog.groups:
        assert tuple(item.depth for item in group.packages) == OBSERVATION_DEPTH_ORDER
        assert (
            tuple(item.target_load.total for item in group.packages)
            == expected_loads[group.capability_family]
        )
        assert len({item.graph.graph_id for item in group.packages}) == 4
        assert len({item.baseline_witness.witness_id for item in group.packages}) == 4
        assert len({item.nuisance_binding.binding_id for item in group.packages}) == 1

    counterfactuals = models.CausalCounterfactualCatalog.model_validate(
        _load("causal_counterfactual_catalog.json")
    )
    assert len(counterfactuals.replays) == 64
    assert Counter(item.counterfactual_kind for item in counterfactuals.replays) == {
        CausalCounterfactualKind.REMOVE_TARGET_MECHANISM: 32,
        CausalCounterfactualKind.BYPASS_TARGET_MECHANISM: 32,
    }
    assert counterfactuals.task_verifier_invocation_count == 64
    assert counterfactuals.mechanism_verifier_invocation_count == 64
    assert counterfactuals.base_invalid_count == 64
    assert counterfactuals.mechanism_unqualified_count == 64
    assert counterfactuals.qualified_invalid_count == 64
    assert all(item.graph_remained_structurally_valid for item in counterfactuals.replays)
    assert all(item.runtime_completed_typed_terminal for item in counterfactuals.replays)
    assert all(item.task_verifier_invoked for item in counterfactuals.replays)
    assert all(not item.counterfactual_base_valid for item in counterfactuals.replays)
    assert all(not item.counterfactual_mechanism_qualified for item in counterfactuals.replays)
    assert all(not item.counterfactual_qualified_valid for item in counterfactuals.replays)

    interpretation = models.OperationalWitnessInterpretation.model_validate(
        _load("operational_witness_interpretation.json")
    )
    assert interpretation.unique_finance_core_count == 8
    assert interpretation.unique_operational_witness_count == 8
    assert interpretation.operational_witness_package_replay_count == 32
    assert interpretation.unique_causal_depth_witness_count == 32
    assert interpretation.independent_finance_witness_surface_claim_count == 8
    assert interpretation.independent_depth_runtime_surface_claim_count == 32


def test_confirmation_payload_is_never_loaded_and_formal_file_hashes_are_bound() -> None:
    catalog_payload = _load("causal_development_catalog.json")
    transition = models.CausalDepthTransition.model_validate(
        _load("prospective_transition_contract.json")
    )
    serialized = (FORMAL_DIR / "causal_development_catalog.json").read_text(encoding="utf-8")
    assert catalog_payload["confirmation_payload_access_count"] == 0
    assert "sealed_confirmation_executable_depth_catalog" not in serialized
    assert "confirmation_payload" not in catalog_payload
    assert "confirmation_catalog" not in catalog_payload
    assert transition.confirmation_payload_loading_authorized is False

    source_root = models.TransitiveSourceRoot.model_validate(_load("transitive_source_root.json"))
    source_paths = {item.relative_path for item in source_root.files}
    assert {
        "src/trusted_synthesis/core/task/causal_capability_depth.py",
        "src/trusted_synthesis/experiments/vtdo_experiment/phase1_v26_capability_public_projection_causal_runtime_models.py",
        "src/trusted_synthesis/experiments/vtdo_experiment/phase1_v26_capability_public_projection_causal_runtime_static_audit.py",
        "src/trusted_synthesis/experiments/vtdo_experiment/phase1_v26_capability_public_projection_causal_runtime_hardening.py",
    } <= source_paths
    assert source_root.file_count == len(source_paths)
    assert source_root.unresolved_trusted_synthesis_import_count == 0

    report = models.CausalDepthHardeningReport.model_validate(_load("report.json"))
    detail_by_name = {item.relative_path: item for item in report.detail_files}
    formal_names = {
        path.name for path in FORMAL_DIR.iterdir() if path.is_file() and path.name != "report.json"
    }
    assert set(detail_by_name) == formal_names
    for filename, binding in detail_by_name.items():
        payload = (FORMAL_DIR / filename).read_bytes()
        assert binding.byte_count == len(payload)
        assert binding.sha256 == hashlib.sha256(payload).hexdigest()
    assert report.provider_calls == 0
    assert report.development_jobs == 0
