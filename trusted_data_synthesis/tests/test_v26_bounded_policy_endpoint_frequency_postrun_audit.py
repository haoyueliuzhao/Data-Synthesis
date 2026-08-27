from __future__ import annotations

import json
import os
from pathlib import Path

import pytest

from trusted_synthesis.experiments.vtdo_experiment import (
    phase1_v26_bounded_policy_endpoint_frequency_execution_models as execution_models,
)
from trusted_synthesis.experiments.vtdo_experiment import (
    phase1_v26_bounded_policy_endpoint_frequency_postrun_audit as audit,
)
from trusted_synthesis.experiments.vtdo_experiment import (
    phase1_v26_bounded_policy_endpoint_frequency_postrun_audit_models as audit_models,
)
from trusted_synthesis.experiments.vtdo_experiment import (
    phase1_v26_bounded_policy_endpoint_frequency_raw_only_recovery_models as recovery_models,
)

PACKAGE_ROOT = Path(__file__).resolve().parents[1]
CANONICAL_PACKAGE_ROOT = Path(
    os.environ.get(
        "TRUSTED_SYNTHESIS_CANONICAL_PACKAGE_ROOT",
        "/home/zhuxinrui/datatmp/projects/Data-Synthesis/trusted_data_synthesis",
    )
)
HISTORICAL_VERIFIER_REPORT = (
    "artifacts/vtdo_experiment/"
    "finance_v26_75_authority_preserving_verifier_qualification_v2_20260819/report.json"
)
SOURCE_PACKAGE_ROOT = (
    PACKAGE_ROOT
    if (PACKAGE_ROOT / HISTORICAL_VERIFIER_REPORT).is_file()
    else CANONICAL_PACKAGE_ROOT
)
ARTIFACT_ROOT = PACKAGE_ROOT / "artifacts" / "vtdo_experiment"
FAILED_DIR = ARTIFACT_ROOT / (
    "finance_v26_164_bounded_policy_endpoint_frequency_execution_v1_20260827"
)
RECOVERY_DIR = ARTIFACT_ROOT / (
    "finance_v26_164_bounded_policy_endpoint_frequency_raw_only_recovery_v3_20260828"
)
FORMAL_AUDIT_DIR = ARTIFACT_ROOT / (
    "finance_v26_165_bounded_policy_endpoint_frequency_postrun_audit_v2_20260828"
)


def _load(path: Path) -> object:
    return json.loads(path.read_text(encoding="utf-8"))


@pytest.fixture(scope="session")
def rebuilt_audit_dir(tmp_path_factory: pytest.TempPathFactory) -> Path:
    output_dir = tmp_path_factory.mktemp("v26_165_rebuild")
    credential = os.environ.pop("DEEPSEEK_API_KEY", None)
    try:
        audit.build_postrun_audit(
            failed_execution_dir=FAILED_DIR,
            recovery_dir=RECOVERY_DIR,
            output_dir=output_dir,
            package_root=SOURCE_PACKAGE_ROOT,
            implementation_root=PACKAGE_ROOT,
        )
    finally:
        if credential is not None:
            os.environ["DEEPSEEK_API_KEY"] = credential
    return output_dir


def test_v26_164_raw_only_recovery_preserves_the_complete_online_denominator() -> None:
    freeze = recovery_models.FailedExecutionFreezeAudit.model_validate(
        _load(RECOVERY_DIR / "failed_execution_freeze_audit.json")
    )
    recovery_report = recovery_models.RawOnlyRecoveryReport.model_validate(
        _load(RECOVERY_DIR / "report.json")
    )
    execution_report = execution_models.BoundedPolicyExecutionReport.model_validate(
        _load(RECOVERY_DIR / "bounded_policy_execution_report.json")
    )
    gate = execution_report.global_integrity_gate_id
    normalization = recovery_models.TypedSemanticRejectionNormalizationAudit.model_validate(
        _load(RECOVERY_DIR / "typed_semantic_rejection_normalization_audit.json")
    )

    assert freeze.complete_raw_count == 360
    assert freeze.direct_checkpoint_count == 358
    assert freeze.typed_semantic_rejection_count == 2
    assert freeze.provider_call_count == freeze.transport_invocation_count == 2_919
    assert freeze.provider_artifact_triple_count == 3 * freeze.provider_call_count
    assert freeze.failed_execution_file_count == 9_143
    assert freeze.failed_execution_byte_count == 64_601_865
    assert freeze.failed_execution_unchanged_after_recovery
    assert freeze.recovery_provider_calls == 0
    assert recovery_report.recovered_measurement_result_count == 360
    assert recovery_report.direct_checkpoint_byte_match_count == 358
    assert recovery_report.typed_semantic_rejection_normalized_count == 2
    assert recovery_report.row_deletion_count == 0
    assert recovery_report.historical_reclassification_count == 0
    assert recovery_report.global_integrity_gate_passed
    assert execution_report.global_integrity_gate_passed
    assert gate == recovery_report.global_integrity_gate_id
    assert execution_report.bounded_policy_terminal_counts == {
        "completed_model_endpoint": 150,
        "model_result_failure": 207,
        "model_typed_rejection": 2,
        "policy_horizon_exhausted": 1,
    }
    assert execution_report.policy_horizon_reason_counts == {
        "ordinary_detour_limit": 1,
        "primary_request_limit": 0,
        "provider_call_limit": 0,
        "rollout_token_limit": 0,
        "transport_invocation_limit": 0,
    }
    assert execution_report.base_valid_count == 106
    assert execution_report.mechanism_qualified_count == 226
    assert execution_report.qualified_valid_count == 106
    assert normalization.before_null_validity_count == 2
    assert normalization.after_explicit_failure_validity_count == 2
    assert normalization.state_mapping_attempt_count == 0


def test_v26_164_mapper_and_frequency_outputs_remain_policy_conditioned() -> None:
    assignments = execution_models.BoundedPolicyAssignmentCatalog.model_validate(
        _load(RECOVERY_DIR / "bounded_policy_assignment_catalog.json")
    )
    mapper = execution_models.MapperExecutionAudit.model_validate(
        _load(RECOVERY_DIR / "mapper_execution_audit.json")
    )
    cells = execution_models.BoundedPolicyCellFrequencyCatalog.model_validate(
        _load(RECOVERY_DIR / "bounded_policy_cell_frequency_catalog.json")
    )
    report = execution_models.BoundedPolicyExecutionReport.model_validate(
        _load(RECOVERY_DIR / "bounded_policy_execution_report.json")
    )

    assert assignments.assignment_count == mapper.formal_assignment_count == 106
    assert assignments.structural_state_count == report.structural_state_count == 53
    assert assignments.empirical_route_signature_count == 57
    assert mapper.mapper_invocation_before_global_gate_count == 0
    assert mapper.policy_horizon_mapping_attempt_count == 0
    assert mapper.production_reference_exact_state_match_count == 106
    assert cells.cell_count == 48
    assert cells.n_total_sum == cells.n_policy_endpoint_sum == 360
    assert cells.n_qualified_sum == 106
    assert cells.q_instantiated_cell_count == 48
    assert cells.pi_instantiated_cell_count == 38
    assert cells.zero_qualified_cell_count == 10
    assert cells.empirical_non_degenerate_cell_count == 27
    assert report.bounded_policy_finite_sample_empirical_frequency_only
    assert not report.unrestricted_natural_agent_distribution_claimed
    assert not report.cross_task_state_probability_claimed
    assert not report.path_causal_effect_claimed
    assert not report.simultaneous_multinomial_coverage_claimed
    assert not report.vtdo_authorized


def test_v26_165_independently_confirms_endpoint_gate_mapper_and_cells() -> None:
    report = audit_models.PostrunAuditReport.model_validate(_load(FORMAL_AUDIT_DIR / "report.json"))
    endpoints = audit_models.IndependentEndpointCatalog.model_validate(
        _load(FORMAL_AUDIT_DIR / "independent_endpoint_catalog.json")
    )
    provider = audit_models.IndependentProviderArtifactAudit.model_validate(
        _load(FORMAL_AUDIT_DIR / "independent_provider_artifact_audit.json")
    )
    gate = audit_models.IndependentGateAudit.model_validate(
        _load(FORMAL_AUDIT_DIR / "independent_gate_audit.json")
    )
    mapper = audit_models.IndependentMapperAudit.model_validate(
        _load(FORMAL_AUDIT_DIR / "independent_mapper_audit.json")
    )
    cells = audit_models.IndependentCellFrequencyAudit.model_validate(
        _load(FORMAL_AUDIT_DIR / "independent_cell_frequency_audit.json")
    )
    boundary = audit_models.RecoveryBoundaryAudit.model_validate(
        _load(FORMAL_AUDIT_DIR / "recovery_boundary_audit.json")
    )

    assert endpoints.row_count == endpoints.endpoint_exact_match_count == 360
    assert endpoints.model_terminal_count == 359
    assert endpoints.policy_horizon_endpoint_count == 1
    assert endpoints.validity_evaluable_count == 360
    assert endpoints.qualified_valid_count == 106
    assert provider.provider_call_count == provider.complete_artifact_triple_count == 2_919
    assert provider.provider_total_tokens == 28_539_733
    assert provider.exact_model_failure_count == 0
    assert provider.thinking_failure_count == 0
    assert provider.usage_failure_count == 0
    assert provider.privacy_failure_count == 0
    assert provider.unresolved_transport_failure_count == 0
    assert provider.stage_two_provider_call_count == 0
    assert gate.exact_gate_match and gate.passed and not gate.failure_ids
    assert mapper.production_reference_exact_state_match_count == 106
    assert mapper.recovered_assignment_exact_match_count == 106
    assert mapper.structural_state_count == 53
    assert mapper.empirical_route_signature_count == 57
    assert cells.exact_report_match_count == 48
    assert cells.q_instantiated_cell_count == 48
    assert cells.pi_instantiated_cell_count == 38
    assert cells.zero_qualified_cell_count == 10
    assert cells.empirical_non_degenerate_cell_count == 27
    assert boundary.failed_execution_unchanged
    assert boundary.direct_checkpoint_byte_match_count == 358
    assert boundary.typed_semantic_rejection_null_to_false_count == 2
    assert boundary.policy_horizon_later_provider_call_count == 0
    assert report.provider_calls == 0
    assert report.final_decision == audit_models.FINAL_DECISION
    assert not report.vtdo_authorized
    assert not report.training_release_or_production_authorized


def test_v26_165_rebuild_is_byte_identical(rebuilt_audit_dir: Path) -> None:
    formal = tuple(sorted(path for path in FORMAL_AUDIT_DIR.iterdir() if path.is_file()))
    rebuilt = tuple(sorted(path for path in rebuilt_audit_dir.iterdir() if path.is_file()))

    assert len(formal) == len(rebuilt) == 8
    assert tuple(path.name for path in formal) == tuple(path.name for path in rebuilt)
    for path in formal:
        assert path.read_bytes() == (rebuilt_audit_dir / path.name).read_bytes()


def test_v26_165_report_and_boundary_mutations_fail_closed() -> None:
    report_payload = _load(FORMAL_AUDIT_DIR / "report.json")
    assert isinstance(report_payload, dict)
    report_payload["vtdo_authorized"] = True
    with pytest.raises(ValueError):
        audit_models.PostrunAuditReport.model_validate(report_payload)

    boundary_payload = _load(FORMAL_AUDIT_DIR / "recovery_boundary_audit.json")
    assert isinstance(boundary_payload, dict)
    boundary_payload["row_deletion_count"] = 1
    with pytest.raises(ValueError):
        audit_models.RecoveryBoundaryAudit.model_validate(boundary_payload)
