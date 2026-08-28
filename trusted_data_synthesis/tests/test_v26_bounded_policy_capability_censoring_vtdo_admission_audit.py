from __future__ import annotations

import json
from pathlib import Path

import pytest
from pydantic import ValidationError

from trusted_synthesis.experiments.vtdo_experiment import (
    phase1_v26_bounded_policy_capability_censoring_vtdo_admission_audit as audit,
)
from trusted_synthesis.experiments.vtdo_experiment import (
    phase1_v26_bounded_policy_capability_censoring_vtdo_admission_audit_models as models,
)

PACKAGE_ROOT = Path(__file__).resolve().parents[1]
FORMAL_DIR = PACKAGE_ROOT / models.OUTPUT_DIR


def _load(name: str) -> object:
    return json.loads((FORMAL_DIR / name).read_text(encoding="utf-8"))


def test_v26_166_empty_directory_rebuild_is_byte_exact(tmp_path: Path) -> None:
    output_dir = tmp_path / "rebuild"
    report = audit.build_audit(package_root=PACKAGE_ROOT, output_dir=output_dir)

    assert report.provider_calls == 0
    assert report.current_vtdo_admitted_cell_count == 0
    assert report.next_stage == "fresh_vtdo_admission_confirmation_preflight_only"
    rebuilt = tuple(sorted(path.name for path in output_dir.glob("*.json")))
    formal = tuple(sorted(path.name for path in FORMAL_DIR.glob("*.json")))
    assert rebuilt == formal
    assert len(rebuilt) == 12
    for name in rebuilt:
        assert (output_dir / name).read_bytes() == (FORMAL_DIR / name).read_bytes()


def test_v26_166_support_survival_and_admission_boundaries() -> None:
    strata = models.CellSupportStratumCatalog.model_validate(
        _load("cell_support_stratum_catalog.json")
    )
    survival = models.CapabilitySurvivalProfileCatalog.model_validate(
        _load("capability_survival_profile_catalog.json")
    )
    admission = models.VTDOAdmissionCatalog.model_validate(_load("vtdo_admission_catalog.json"))
    coverage = models.CoverageGapRegistry.model_validate(_load("coverage_gap_registry.json"))

    assert (
        strata.valid_support_absent_count,
        strata.single_valid_observation_count,
        strata.observed_single_state_support_count,
        strata.observed_multistate_support_count,
    ) == (10, 8, 3, 27)
    assert strata.absent_cell_signatures == models.ABSENT_CELL_SIGNATURES
    assert strata.single_state_cell_signatures == models.SINGLE_STATE_CELL_SIGNATURES
    assert survival.first_authorized_blocker_counts == {
        "action_entry": 22,
        "answer_semantics": 1,
        "citation": 2,
        "evidence_support": 37,
        "final_abi": 13,
        "none_qualified_survivor": 106,
        "operation_lineage": 54,
        "policy_horizon": 1,
        "program_closure": 124,
    }
    assert survival.invalid_trajectory_vtdo_mapping_count == 0
    assert admission.state_support_existence_count == 27
    assert admission.frequency_estimability_count == 0
    assert admission.contribution_estimability_count == 0
    assert coverage.valid_support_absent_count == 10
    assert coverage.weak_support_count == 11
    assert coverage.compiler_intervention_count == 0


def test_v26_166_terminal_matrix_and_typed_rejection_boundary() -> None:
    terminal = models.TerminalEndpointSchemaAudit.model_validate(
        _load("terminal_endpoint_schema_audit.json")
    )
    typed = models.TypedSemanticRejectionBoundaryAudit.model_validate(
        _load("typed_semantic_rejection_boundary_audit.json")
    )

    assert terminal.exact_null_policy_match_count == 8
    assert {item.case_name for item in terminal.cases} == {
        "completed_endpoint",
        "instrument_endpoint",
        "measurement_support_exit",
        "model_result_failure",
        "policy_horizon",
        "privacy_endpoint",
        "transport_endpoint",
        "typed_semantic_rejection",
    }
    assert len(typed.rows) == 2
    assert all(not item.mechanism_endpoint_qualification for item in typed.rows)
    assert all(not item.mechanism_event_evaluable for item in typed.rows)
    assert all(not item.task_verifier_invoked for item in typed.rows)
    assert typed.unconditional_mechanism_occurrence_rate_claimed is False


def test_v26_166_destructive_mutations_fail_closed() -> None:
    strata_payload = _load("cell_support_stratum_catalog.json")
    assert isinstance(strata_payload, dict)
    zero_index = next(
        index
        for index, row in enumerate(strata_payload["rows"])
        if row["stratum"] == "valid_support_absent"
    )
    strata_payload["rows"][zero_index]["observed_state_ids"] = ["imputed-state"]
    strata_payload["rows"][zero_index]["observed_state_count"] = 1
    with pytest.raises(ValidationError):
        models.CellSupportStratumCatalog.model_validate(strata_payload)

    typed_payload = _load("typed_semantic_rejection_boundary_audit.json")
    assert isinstance(typed_payload, dict)
    typed_payload["rows"][0]["task_verifier_invoked"] = True
    with pytest.raises(ValidationError):
        models.TypedSemanticRejectionBoundaryAudit.model_validate(typed_payload)

    admission_payload = _load("vtdo_admission_catalog.json")
    assert isinstance(admission_payload, dict)
    admission_payload["rows"][0]["frequency_estimability"] = True
    with pytest.raises(ValidationError):
        models.VTDOAdmissionCatalog.model_validate(admission_payload)

    confirmation_payload = _load("fresh_confirmation_protocol.json")
    assert isinstance(confirmation_payload, dict)
    confirmation_payload["current_27_multistate_cells_may_define_selection_frame"] = True
    with pytest.raises(ValidationError):
        models.FreshConfirmationProtocol.model_validate(confirmation_payload)
