from __future__ import annotations

import json
from pathlib import Path

import pytest

from trusted_synthesis.experiments.vtdo_experiment import (
    phase1_v26_capability_validity_decomposition_audit as audit,
)

PACKAGE_ROOT = Path(__file__).resolve().parents[1]
FORMAL_DIR = PACKAGE_ROOT / audit.OUTPUT_DIR


@pytest.fixture(scope="session")
def rebuilt_dir(tmp_path_factory: pytest.TempPathFactory) -> Path:
    output_dir = tmp_path_factory.mktemp("v26_147_rebuild")
    audit.build_validity_decomposition_audit(
        package_root=PACKAGE_ROOT,
        implementation_root=PACKAGE_ROOT,
        output_dir=output_dir,
    )
    return output_dir


def _load(path: Path) -> dict[str, object]:
    value = json.loads(path.read_text(encoding="utf-8"))
    assert isinstance(value, dict)
    return value


def test_v26_147_rebuild_is_byte_identical(rebuilt_dir: Path) -> None:
    formal = tuple(sorted(path for path in FORMAL_DIR.iterdir() if path.is_file()))
    rebuilt = tuple(sorted(path for path in rebuilt_dir.iterdir() if path.is_file()))
    assert tuple(path.name for path in formal) == tuple(path.name for path in rebuilt)
    assert len(formal) == 10
    for path in formal:
        assert path.read_bytes() == (rebuilt_dir / path.name).read_bytes()


def test_v26_147_read_only_decomposition_and_task_summaries_are_closed() -> None:
    report = audit.ValidityDecompositionReport.model_validate(_load(FORMAL_DIR / "report.json"))
    catalog = audit.ValidityDecompositionCatalog.model_validate(
        _load(FORMAL_DIR / "validity_decomposition_catalog.json")
    )
    tasks = audit.TaskLevelSummaryAudit.model_validate(
        _load(FORMAL_DIR / "task_level_summary_audit.json")
    )
    groups = audit.MechanismTierSummaryAudit.model_validate(
        _load(FORMAL_DIR / "mechanism_tier_summary_audit.json")
    )
    assert report.complete_raw_model_outcome_count == 93
    assert report.support_exit_count == 3
    assert report.historical_valid_count == 17
    assert report.historical_invalid_count == 76
    assert catalog.final_endpoint_observed_count == 54
    assert catalog.decimal_representation_only_difference_count == 11
    assert catalog.runtime_support_complete_model_citation_incomplete_count == 54
    assert catalog.diagnostic_base_valid_count == 0
    assert catalog.diagnostic_mechanism_success_count == 75
    assert catalog.diagnostic_qualified_valid_count == 0
    assert all(row.historical_reclassified is False for row in catalog.model_rows)
    assert all(row.counterfactual_diagnostic_only is True for row in catalog.model_rows)
    assert all(row.validity_evaluable is True for row in catalog.model_rows)
    assert all(row.validity_evaluable is False for row in catalog.support_exit_rows)
    assert all(row.diagnostic_base_validity is None for row in catalog.support_exit_rows)
    assert len(tasks.task_rows) == 12
    assert sum(row.evaluable_model_outcome_count for row in tasks.task_rows) == 93
    assert sum(row.support_exit_count for row in tasks.task_rows) == 3
    assert all(row.exact_design_replica_count == 8 for row in tasks.task_rows)
    assert len(groups.mechanism_rows) == 4
    assert len(groups.tier_rows) == 3


def test_v26_147_failure_localization_immutability_and_transition_are_closed() -> None:
    localization = audit.FailureLocalizationAudit.model_validate(
        _load(FORMAL_DIR / "failure_localization_audit.json")
    )
    immutability = audit.HistoricalImmutabilityAudit.model_validate(
        _load(FORMAL_DIR / "historical_immutability_audit.json")
    )
    destructive = audit.DestructiveAudit.model_validate(
        _load(FORMAL_DIR / "destructive_audit.json")
    )
    transition = audit.ProspectiveTransitionContract.model_validate(
        _load(FORMAL_DIR / "prospective_transition_contract.json")
    )
    assert localization.historical_invalid_first_failure_counts == {
        "action_abi": 1,
        "answer_schema": 37,
        "final_abi": 6,
        "program_closure": 22,
        "terminal_verification": 10,
    }
    assert localization.old_answer_projection_failure_count == 29
    assert localization.decimal_representation_only_difference_count == 11
    assert localization.old_citation_complete_count == 54
    assert localization.model_citation_complete_count == 0
    assert localization.historical_valid_model_citation_incomplete_count == 17
    assert immutability.historical_terminal_reclassified_count == 0
    assert immutability.historical_validity_reclassified_count == 0
    assert immutability.support_exit_entered_validity_denominator_count == 0
    assert destructive.mutation_count == destructive.rejected_count == 20
    assert transition.next_permitted_stage == audit.NEXT_STAGE
    assert transition.verifier_vnext_contract_freeze_authorized is True
    assert transition.provider_calls_authorized is False
    assert transition.new_capability_population_or_identity_materialization_authorized is False
    assert transition.capability_or_reachability_execution_authorized is False
    assert transition.state_mapping_authorized is False
