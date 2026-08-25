from __future__ import annotations

import json
from pathlib import Path

import pytest

from trusted_synthesis.experiments.vtdo_experiment import (
    phase1_v26_joint_support_verifier_preflight as preflight,
)

PACKAGE_ROOT = Path(__file__).resolve().parents[1]
FORMAL_DIR = PACKAGE_ROOT / preflight.OUTPUT_DIR


@pytest.fixture(scope="session")
def rebuilt_dir(tmp_path_factory: pytest.TempPathFactory) -> Path:
    output_dir = tmp_path_factory.mktemp("v26_149_rebuild")
    preflight.build_joint_support_verifier_preflight(
        package_root=PACKAGE_ROOT,
        implementation_root=PACKAGE_ROOT,
        output_dir=output_dir,
    )
    return output_dir


def _load(path: Path) -> dict[str, object]:
    value = json.loads(path.read_text(encoding="utf-8"))
    assert isinstance(value, dict)
    return value


def test_v26_149_rebuild_is_byte_identical(rebuilt_dir: Path) -> None:
    formal = tuple(sorted(path for path in FORMAL_DIR.iterdir() if path.is_file()))
    rebuilt = tuple(sorted(path for path in rebuilt_dir.iterdir() if path.is_file()))
    assert tuple(path.name for path in formal) == tuple(path.name for path in rebuilt)
    assert len(formal) == 9
    for path in formal:
        assert path.read_bytes() == (rebuilt_dir / path.name).read_bytes()


def test_v26_149_joint_fixture_computes_support_and_validity_boundaries() -> None:
    authority = preflight._authority_binding(PACKAGE_ROOT)
    contract = preflight._joint_contract(authority)
    fixture = preflight._positive_fixture(contract)
    rows = {row.fixture_name: row for row in fixture.rows}
    assert fixture.fixture_count == fixture.passed_count == 19
    assert rows["decimal_string_number_equal"].qualified_valid is True
    assert rows["true_numeric_error"].base_valid is False
    assert rows["base_valid_mechanism_invalid"].qualified_valid is False
    assert rows["base_invalid_mechanism_event_present"].mechanism_success is True
    assert (
        rows["failed_observation_replans_without_baseline"].baseline_classifier_invocation_count
        == 0
    )
    assert rows["successful_progress_skips_baseline"].baseline_classifier_invocation_count == 0
    assert rows["successful_no_progress_invokes_baseline"].baseline_classifier_invocation_count == 1
    assert rows["context_action_change_complete"].qualified_valid is True


def test_v26_149_ineligible_rows_never_invoke_task_verifier_or_map_state() -> None:
    authority = preflight._authority_binding(PACKAGE_ROOT)
    fixture = preflight._positive_fixture(preflight._joint_contract(authority))
    ineligible = tuple(row for row in fixture.rows if not row.validity_evaluable)
    assert len(ineligible) == 4
    for row in ineligible:
        assert row.task_verifier_invocation_count == 0
        assert row.base_valid is None
        assert row.mechanism_success is None
        assert row.qualified_valid is None
        assert row.state_mapping_eligible is False
    assert {row.endpoint_disposition for row in ineligible} == {
        "measurement_support_exit",
        "model_endpoint_unobserved",
        "instrument_failure",
        "privacy_rejection",
    }


def test_v26_149_formal_contract_destructive_and_transition_are_closed() -> None:
    report = preflight.JointPreflightReport.model_validate(_load(FORMAL_DIR / "report.json"))
    contract = preflight.JointSupportValidityContract.model_validate(
        _load(FORMAL_DIR / "joint_support_validity_contract.json")
    )
    fixture = preflight.PositiveFixtureAudit.model_validate(
        _load(FORMAL_DIR / "positive_fixture_audit.json")
    )
    ordering = preflight.StageOrderingAudit.model_validate(
        _load(FORMAL_DIR / "stage_ordering_audit.json")
    )
    destructive = preflight.DestructiveAudit.model_validate(
        _load(FORMAL_DIR / "destructive_audit.json")
    )
    transition = preflight.ProspectiveTransitionContract.model_validate(
        _load(FORMAL_DIR / "prospective_transition_contract.json")
    )
    assert report.positive_fixture_count == fixture.fixture_count == 19
    assert contract.state_machine_order[4:7] == (
        "measurement_support",
        "model_endpoint",
        "validity_eligibility",
    )
    assert ordering.ineligible_later_stage_invocation_count == 0
    assert destructive.mutation_count == destructive.rejected_count == 20
    assert transition.next_permitted_stage == preflight.NEXT_STAGE
    assert transition.fresh_capability_population_runner_preflight_authorized is True
    assert transition.provider_calls_authorized is False
    assert transition.capability_execution_authorized is False
    assert transition.reachability_identity_or_execution_authorized is False
    assert transition.state_mapping_authorized is False
