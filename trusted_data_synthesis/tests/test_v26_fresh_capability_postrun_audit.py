from __future__ import annotations

import json
from pathlib import Path

import pytest

from trusted_synthesis.experiments.vtdo_experiment import (
    phase1_v26_fresh_capability_postrun_audit as audit,
)

PACKAGE_ROOT = Path(__file__).resolve().parents[1]
EXECUTION_DIR = PACKAGE_ROOT / audit.execution.OUTPUT_DIR
FORMAL_DIR = PACKAGE_ROOT / audit.OUTPUT_DIR


def _load(path: Path) -> object:
    return json.loads(path.read_text(encoding="utf-8"))


@pytest.fixture(scope="session")
def rebuilt_dir(tmp_path_factory: pytest.TempPathFactory) -> Path:
    output_dir = tmp_path_factory.mktemp("v26_152_rebuild")
    audit.build_postrun_audit(
        package_root=PACKAGE_ROOT,
        implementation_root=PACKAGE_ROOT,
        execution_dir=EXECUTION_DIR,
        output_dir=output_dir,
    )
    return output_dir


def test_v26_152_rebuild_is_byte_identical(rebuilt_dir: Path) -> None:
    formal = tuple(sorted(path for path in FORMAL_DIR.iterdir() if path.is_file()))
    rebuilt = tuple(sorted(path for path in rebuilt_dir.iterdir() if path.is_file()))
    assert tuple(path.name for path in formal) == tuple(path.name for path in rebuilt)
    assert len(formal) == 9
    for path in formal:
        assert path.read_bytes() == (rebuilt_dir / path.name).read_bytes()


def test_v26_152_formal_gate_estimand_and_transition_are_closed() -> None:
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

    assert source.replay_pass_count == source.replayed_file_count == 10_125
    assert provider.raw_execution_count == provider.checkpoint_result_count == 96
    assert provider.validated_provider_pair_count == provider.transport_invocation_count == 879
    assert gate.passed is gate.capability_estimand_authorized is True
    assert gate.failure_ids == ()
    assert (estimand.base_valid_count, estimand.mechanism_qualified_count) == (31, 74)
    assert estimand.qualified_valid_count == 31
    assert estimand.mechanisms_with_qualified_task_support == 4
    assert report.status == "capability_postrun_audit_passed"
    assert transition.next_permitted_stage == audit.NEXT_STAGE
    assert transition.frozen_reachability_source_population_id == (
        audit.EXPECTED_FROZEN_REACHABILITY_POPULATION_ID
    )
    assert transition.reachability_provider_calls_authorized is False
    assert transition.reachability_execution_authorized is False
    assert transition.state_mapping_identity_or_execution_authorized is False


def test_v26_152_projection_and_validity_decomposition_are_independent() -> None:
    projection = audit.IndependentProjectionAudit.model_validate(
        _load(FORMAL_DIR / "independent_projection_audit.json")
    )
    decomposition = audit.IndependentValidityDecompositionAudit.model_validate(
        _load(FORMAL_DIR / "validity_decomposition_audit.json")
    )

    assert projection.measurement_result_count == 96
    assert projection.exact_checkpoint_projection_match_count == 96
    assert projection.exact_aggregate_projection_match_count == 96
    assert projection.exact_joint_result_match_count == 96
    assert projection.exact_prompt_audit_match_count == 96
    assert len(projection.base_check_pass_counts) == projection.required_base_check_count == 14
    assert projection.independent_projection_used_execution_projector is False
    assert projection.independent_projection_used_execution_gate is False
    assert projection.independent_projection_used_execution_summary_helpers is False
    assert decomposition.formal_report_aggregate_match_count == 18
    assert decomposition.qualified_equals_base_and_mechanism_count == 96
    assert decomposition.support_or_integrity_rows_with_nonnull_validity == 0
    assert decomposition.state_mapping_eligible_count == decomposition.qualified_valid_count == 31


def test_v26_152_gate_and_transition_mutations_fail_closed() -> None:
    gate = audit.IndependentMeasurementGateAudit.model_validate(
        _load(FORMAL_DIR / "independent_measurement_gate_audit.json")
    )
    gate_payload = gate.model_dump(mode="python")
    gate_payload["instrument_failure_count"] = 1
    provisional = audit.IndependentMeasurementGateAudit.model_construct(**gate_payload)
    gate_payload["audit_id"] = audit._identity(  # noqa: SLF001
        provisional,
        "audit_id",
        "finance_v26_fresh_capability_independent_measurement_gate:",
    )
    with pytest.raises(ValueError, match="Measurement Gate changed"):
        audit.IndependentMeasurementGateAudit.model_validate(gate_payload)

    transition_payload = _load(FORMAL_DIR / "prospective_transition_contract.json")
    assert isinstance(transition_payload, dict)
    transition_payload["reachability_execution_authorized"] = True
    with pytest.raises(ValueError):
        audit.ProspectiveTransitionContract.model_validate(transition_payload)
