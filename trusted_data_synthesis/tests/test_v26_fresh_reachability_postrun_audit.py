from __future__ import annotations

import json
from pathlib import Path

import pytest

from trusted_synthesis.experiments.vtdo_experiment import (
    phase1_v26_fresh_reachability_postrun_audit as audit,
)

PACKAGE_ROOT = Path(__file__).resolve().parents[1]
EXECUTION_DIR = PACKAGE_ROOT / audit.execution.OUTPUT_DIR
FORMAL_DIR = PACKAGE_ROOT / audit.OUTPUT_DIR


def _load(path: Path) -> object:
    return json.loads(path.read_text(encoding="utf-8"))


@pytest.fixture(scope="session")
def rebuilt_dir(tmp_path_factory: pytest.TempPathFactory) -> Path:
    output_dir = tmp_path_factory.mktemp("v26_155_rebuild")
    audit.build_postrun_audit(
        package_root=PACKAGE_ROOT,
        implementation_root=PACKAGE_ROOT,
        execution_dir=EXECUTION_DIR,
        output_dir=output_dir,
    )
    return output_dir


def test_v26_155_rebuild_is_byte_identical(rebuilt_dir: Path) -> None:
    formal = tuple(sorted(path for path in FORMAL_DIR.iterdir() if path.is_file()))
    rebuilt = tuple(sorted(path for path in rebuilt_dir.iterdir() if path.is_file()))
    assert tuple(path.name for path in formal) == tuple(path.name for path in rebuilt)
    assert len(formal) == 10
    for path in formal:
        assert path.read_bytes() == (rebuilt_dir / path.name).read_bytes()


def test_v26_155_gate_estimands_and_transition_preserve_the_failed_boundary() -> None:
    report = audit.PostrunAuditReport.model_validate(_load(FORMAL_DIR / "report.json"))
    source = audit.PostrunSourceReplayAudit.model_validate(
        _load(FORMAL_DIR / "source_replay_audit.json")
    )
    provider = audit.IndependentProviderArtifactAudit.model_validate(
        _load(FORMAL_DIR / "independent_provider_artifact_audit.json")
    )
    gate = audit.IndependentMeasurementGateAudit.model_validate(
        _load(FORMAL_DIR / "independent_measurement_gate_audit.json")
    )
    estimand = audit.IndependentEstimandAudit.model_validate(
        _load(FORMAL_DIR / "independent_estimand_audit.json")
    )
    transition = audit.ProspectiveTransitionContract.model_validate(
        _load(FORMAL_DIR / "prospective_transition_contract.json")
    )

    assert source.execution_transitive_file_count == 10_156
    assert source.replayed_file_count == (
        source.execution_transitive_file_count + source.execution_file_count + 1
    )
    assert provider.raw_execution_count == provider.checkpoint_result_count == 360
    assert provider.provider_call_count == provider.validated_provider_pair_count
    assert provider.transport_invocation_count >= provider.provider_call_count
    assert gate.passed is gate.reachability_estimands_authorized is False
    assert gate.state_mapping_eligibility_estimand_authorized is False
    assert "measurement_support_exit_zero" in gate.failure_ids
    assert "model_endpoint_360_of_360" in gate.failure_ids
    assert estimand.reachability_estimands_authorized is False
    assert estimand.unconditional_task_weighted_qualified_fraction is None
    assert estimand.conditioned_path_weighted_qualified_fraction is None
    assert report.status == "reachability_postrun_audit_closed_failed_gate"
    assert report.measurement_support_exit_count > 0
    assert report.qualified_valid_count > 0
    assert transition.next_permitted_stage == audit.NEXT_STAGE
    assert transition.reachability_estimands_authorized is False
    assert transition.valid_only_observed_state_mapping_preflight_authorized is True
    assert transition.state_mapping_execution_authorized is False


def test_v26_155_projection_validity_and_support_are_independent() -> None:
    projection = audit.IndependentProjectionAudit.model_validate(
        _load(FORMAL_DIR / "independent_projection_audit.json")
    )
    decomposition = audit.IndependentValidityDecompositionAudit.model_validate(
        _load(FORMAL_DIR / "validity_decomposition_audit.json")
    )
    support = audit.SupportBoundaryAudit.model_validate(
        _load(FORMAL_DIR / "support_boundary_audit.json")
    )

    assert projection.measurement_result_count == 360
    assert projection.exact_checkpoint_projection_match_count == 360
    assert projection.exact_aggregate_projection_match_count == 360
    assert projection.exact_joint_result_match_count == 360
    assert projection.exact_route_binding_match_count == 360
    assert (
        projection.exact_prompt_audit_match_count + projection.null_prompt_audit_match_count == 360
    )
    assert len(projection.base_check_pass_counts) == projection.required_base_check_count == 14
    assert projection.independent_projection_used_execution_projector is False
    assert projection.independent_projection_used_execution_gate is False
    assert projection.independent_projection_used_execution_summary_helpers is False
    assert decomposition.qualified_equals_base_and_mechanism_count == 360
    assert decomposition.support_or_integrity_rows_with_nonnull_validity == 0
    assert decomposition.state_mapping_eligible_count == decomposition.qualified_valid_count
    assert support.measurement_support_exit_count == decomposition.measurement_support_exit_count
    assert (
        support.raw_native_instrument_integrity_true_count == support.measurement_support_exit_count
    )
    assert support.formal_projected_instrument_failure_overlap_count == (
        support.measurement_support_exit_count
    )
    assert support.later_provider_call_count == 0
    assert support.reachability_frequency_estimate_authorized is False


def test_v26_155_gate_support_and_transition_mutations_fail_closed() -> None:
    gate = audit.IndependentMeasurementGateAudit.model_validate(
        _load(FORMAL_DIR / "independent_measurement_gate_audit.json")
    )
    gate_payload = gate.model_dump(mode="python")
    gate_payload["measurement_support_exit_count"] = 0
    provisional_gate = audit.IndependentMeasurementGateAudit.model_construct(**gate_payload)
    gate_payload["audit_id"] = audit._identity(  # noqa: SLF001
        provisional_gate,
        "audit_id",
        "finance_v26_fresh_reachability_independent_measurement_gate:",
    )
    with pytest.raises(ValueError, match="Measurement Gate changed"):
        audit.IndependentMeasurementGateAudit.model_validate(gate_payload)

    support_payload = _load(FORMAL_DIR / "support_boundary_audit.json")
    assert isinstance(support_payload, dict)
    support_payload["reachability_frequency_estimate_authorized"] = True
    with pytest.raises(ValueError, match="support-boundary audit changed"):
        audit.SupportBoundaryAudit.model_validate(support_payload)

    transition_payload = _load(FORMAL_DIR / "prospective_transition_contract.json")
    assert isinstance(transition_payload, dict)
    transition_payload["qualified_valid_count"] = 0
    with pytest.raises(ValueError, match="transition authorization changed"):
        audit.ProspectiveTransitionContract.model_validate(transition_payload)
