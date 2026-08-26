from __future__ import annotations

import json
from pathlib import Path

import pytest

from trusted_synthesis.experiments.vtdo_experiment import (
    phase1_v26_valid_only_reachability_state_mapping_execution as mapping_execution,
)
from trusted_synthesis.experiments.vtdo_experiment import (
    phase1_v26_valid_only_reachability_state_mapping_postrun_audit as mapping_audit,
)
from trusted_synthesis.experiments.vtdo_experiment import (
    phase1_v26_valid_only_reachability_state_mapping_preflight as mapping_preflight,
)

PACKAGE_ROOT = Path(__file__).resolve().parents[1]
PREFLIGHT_DIR = PACKAGE_ROOT / mapping_preflight.OUTPUT_DIR
EXECUTION_DIR = PACKAGE_ROOT / mapping_execution.OUTPUT_DIR
AUDIT_DIR = PACKAGE_ROOT / mapping_audit.OUTPUT_DIR
REACHABILITY_EXECUTION_DIR = PACKAGE_ROOT / mapping_audit.reachability_execution.OUTPUT_DIR
REACHABILITY_POSTRUN_DIR = PACKAGE_ROOT / mapping_audit.reachability_postrun.OUTPUT_DIR


def _load(path: Path) -> object:
    return json.loads(path.read_text(encoding="utf-8"))


@pytest.fixture(scope="session")
def rebuilt_audit_dir(tmp_path_factory: pytest.TempPathFactory) -> Path:
    output_dir = tmp_path_factory.mktemp("v26_158_rebuild")
    mapping_audit.build_postrun_audit(
        package_root=PACKAGE_ROOT,
        implementation_root=PACKAGE_ROOT,
        reachability_execution_dir=REACHABILITY_EXECUTION_DIR,
        reachability_postrun_dir=REACHABILITY_POSTRUN_DIR,
        mapping_preflight_dir=PREFLIGHT_DIR,
        mapping_execution_dir=EXECUTION_DIR,
        output_dir=output_dir,
    )
    return output_dir


def test_v26_156_preflight_freezes_candidates_without_mapping() -> None:
    report = mapping_preflight.ValidOnlyMappingPreflightReport.model_validate(
        _load(PREFLIGHT_DIR / "report.json")
    )
    manifest = mapping_preflight.ValidOnlyMappingCandidateManifest.model_validate(
        _load(PREFLIGHT_DIR / "candidate_manifest.json")
    )
    audit = mapping_preflight.ValidOnlyMappingPreflightAudit.model_validate(
        _load(PREFLIGHT_DIR / "preflight_audit.json")
    )
    destructive = mapping_preflight.MappingDestructiveAudit.model_validate(
        _load(PREFLIGHT_DIR / "destructive_audit.json")
    )
    runner = mapping_preflight.ValidOnlyMappingRunnerContract.model_validate(
        _load(PREFLIGHT_DIR / "runner_contract.json")
    )
    transition = mapping_preflight.ProspectiveTransitionContract.model_validate(
        _load(PREFLIGHT_DIR / "prospective_transition_contract.json")
    )

    assert report.qualified_candidate_count == manifest.qualified_candidate_count
    assert manifest.qualified_candidate_count == audit.qualified_candidate_count
    assert manifest.exact_reachability_denominator == 360
    assert manifest.state_assignment_count == manifest.structural_state_count == 0
    assert audit.actual_state_assignment_count == audit.actual_structural_state_count == 0
    assert all(item.qualified_validity is True for item in manifest.candidates)
    assert all(item.state_mapping_eligible is True for item in manifest.candidates)
    assert all(item.structural_state_id is None for item in manifest.candidates)
    assert all(item.state_assignment_id is None for item in manifest.candidates)
    assert destructive.mutation_count == destructive.rejected_count == 20
    assert runner.exact_candidate_denominator == manifest.qualified_candidate_count
    assert runner.provider_calls == runner.stage_two_provider_calls == 0
    assert transition.state_mapping_execution_authorized is True
    assert transition.provider_calls_authorized is False
    assert transition.reachability_frequency_estimand_authorized is False


def test_v26_157_maps_each_qualified_candidate_once_and_only_once() -> None:
    report = mapping_execution.ValidOnlyMappingExecutionReport.model_validate(
        _load(EXECUTION_DIR / "report.json")
    )
    catalog = mapping_execution.StateAssignmentCatalog.model_validate(
        _load(EXECUTION_DIR / "assignment_catalog.json")
    )
    integrity = mapping_execution.MappingExecutionIntegrityAudit.model_validate(
        _load(EXECUTION_DIR / "execution_integrity_audit.json")
    )
    support = mapping_execution.ObservedStateSupportAudit.model_validate(
        _load(EXECUTION_DIR / "observed_state_support_audit.json")
    )
    transition = mapping_execution.ProspectiveTransitionContract.model_validate(
        _load(EXECUTION_DIR / "prospective_transition_contract.json")
    )

    assert report.assignment_count == catalog.assignment_count
    assert report.assignment_count == integrity.exact_candidate_count
    assert report.assignment_count == integrity.mapper_invocation_count
    assert report.assignment_count == integrity.exact_eight_parent_binding_count
    assert all(item.qualified_validity is True for item in catalog.assignments)
    assert all(item.valid_only_gate_crossed is True for item in catalog.assignments)
    assert all(item.static_path_used_as_empirical_state is False for item in catalog.assignments)
    assert integrity.support_exit_mapping_attempt_count == 0
    assert integrity.instrument_failure_mapping_attempt_count == 0
    assert integrity.privacy_failure_mapping_attempt_count == 0
    assert integrity.base_invalid_mapping_attempt_count == 0
    assert integrity.mechanism_unqualified_mapping_attempt_count == 0
    assert support.reachability_frequency_estimand_authorized is False
    assert support.state_probability_distribution_authorized is False
    assert all(item.frequency_or_probability_estimate is None for item in support.task_summaries)
    assert transition.independent_raw_remapping_audit_authorized is True
    assert transition.provider_calls_authorized is False


def test_v26_158_independently_remaps_raw_and_closes_claims() -> None:
    report = mapping_audit.ValidOnlyMappingPostrunAuditReport.model_validate(
        _load(AUDIT_DIR / "report.json")
    )
    remap = mapping_audit.IndependentRawRemappingAudit.model_validate(
        _load(AUDIT_DIR / "independent_raw_remapping_audit.json")
    )
    binding = mapping_audit.IndependentAssignmentBindingAudit.model_validate(
        _load(AUDIT_DIR / "independent_assignment_binding_audit.json")
    )
    state = mapping_audit.IndependentObservedStateAudit.model_validate(
        _load(AUDIT_DIR / "independent_observed_state_audit.json")
    )
    outcome = mapping_audit.OutcomeInterpretation.model_validate(
        _load(AUDIT_DIR / "outcome_interpretation.json")
    )
    destructive = mapping_audit.DestructiveAudit.model_validate(
        _load(AUDIT_DIR / "destructive_audit.json")
    )
    decision = mapping_audit.FinalDecisionContract.model_validate(
        _load(AUDIT_DIR / "final_decision_contract.json")
    )

    assert report.assignment_count == remap.exact_candidate_count
    assert remap.exact_assignment_byte_match_count == report.assignment_count
    assert remap.exact_structural_state_id_match_count == report.assignment_count
    assert remap.exact_route_projection_id_match_count == report.assignment_count
    assert remap.used_preflight_trajectory_projection_helper is False
    assert remap.used_preflight_runtime_alias_helper is False
    assert remap.used_execution_assignment_helper is False
    assert remap.trusted_saved_assignment_fields_as_mapper_inputs is False
    assert binding.exact_assignment_count == report.assignment_count
    assert binding.support_exit_assignment_count == 0
    assert binding.instrument_failure_assignment_count == 0
    assert binding.privacy_failure_assignment_count == 0
    assert binding.base_invalid_assignment_count == 0
    assert binding.mechanism_unqualified_assignment_count == 0
    assert state.reachability_measurement_gate_passed is False
    assert state.reachability_frequency_estimand_authorized is False
    assert outcome.empirical_multiple_state_existence_supported == (
        report.tasks_with_multiple_observed_qualified_states > 0
    )
    assert destructive.mutation_count == destructive.rejected_count == 16
    assert decision.valid_only_state_mapping_evidence_frozen is True
    assert decision.provider_calls_authorized is False
    assert decision.reachability_frequency_estimand_authorized is False
    assert decision.state_probability_distribution_authorized is False


def test_v26_158_rebuild_is_byte_identical(rebuilt_audit_dir: Path) -> None:
    formal = tuple(sorted(path for path in AUDIT_DIR.iterdir() if path.is_file()))
    rebuilt = tuple(sorted(path for path in rebuilt_audit_dir.iterdir() if path.is_file()))
    assert tuple(path.name for path in formal) == tuple(path.name for path in rebuilt)
    assert len(formal) == 8
    for path in formal:
        assert path.read_bytes() == (rebuilt_audit_dir / path.name).read_bytes()
