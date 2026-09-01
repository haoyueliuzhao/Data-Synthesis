from __future__ import annotations

import inspect
import json
from pathlib import Path
from typing import Any

import pytest

from trusted_synthesis.core.task import (
    fresh_artifact_backed_terminal_to_outcome_integration as integration,
)
from trusted_synthesis.experiments.vtdo_experiment import (
    phase1_v26_fresh_artifact_backed_terminal_to_outcome_integration_repair_models as models,
)
from trusted_synthesis.experiments.vtdo_experiment import (
    phase1_v26_fresh_artifact_backed_terminal_to_outcome_integration_repair_preflight as preflight,
)

PACKAGE_ROOT = Path(__file__).resolve().parents[1]
REPOSITORY_ROOT = PACKAGE_ROOT.parent
AUDIT_PATH = PACKAGE_ROOT / (
    "tests/fixtures/v26_196_terminal_to_outcome_integration_repair_audit.txt"
)


def _load(path: Path) -> Any:
    return json.loads(path.read_bytes())


@pytest.fixture(scope="module")
def built(
    tmp_path_factory: pytest.TempPathFactory,
) -> tuple[Path, models.RepairPreflightReport]:
    output = tmp_path_factory.mktemp("v26-197") / "formal"
    report = preflight.build(
        repository_root=REPOSITORY_ROOT,
        audit_path=AUDIT_PATH,
        output_dir=output,
    )
    return output, report


def test_exact_external_authorization_and_predecessor_freeze(
    built: tuple[Path, models.RepairPreflightReport],
) -> None:
    output, report = built
    authorization = _load(output / "external_repair_authorization.json")
    freeze = _load(output / "predecessor_freeze_audit.json")
    assert authorization["audit_sha256"] == preflight.EXPECTED_EXTERNAL_AUDIT_SHA256
    assert authorization["audit_byte_count"] == preflight.EXPECTED_EXTERNAL_AUDIT_BYTES
    assert freeze["v196_report_id"] == preflight.V196_REPORT_ID
    assert freeze["v196_transition_id"] == preflight.V196_TRANSITION_ID
    assert freeze["v196_file_match_count"] == 13
    assert freeze["six_authority_identity_match_count"] == 6
    assert freeze["historical_mutation_count"] == 0
    assert report.six_authority_identity_change_count == 0


def test_successor_kernel_has_authorization_ingress_and_no_terminal_argument(
    built: tuple[Path, models.RepairPreflightReport],
) -> None:
    output, report = built
    contract = _load(output / "terminal_to_outcome_integration_contract.json")
    binding = _load(output / "integration_implementation_binding.json")
    constructor = inspect.signature(integration.FreshOutcomeIntegratedExecutionKernel)
    completion = inspect.signature(integration.FreshOutcomeIntegratedExecutionKernel.complete_job)
    assert "authorization" in constructor.parameters
    assert "authorization_bytes" in constructor.parameters
    assert "terminal_kind" not in completion.parameters
    assert contract["kernel_owned_dispatcher_required"] is True
    assert contract["caller_supplied_terminal_forbidden"] is True
    assert contract["fixture_complete_forbidden"] is True
    assert contract["predecessor_execution_identity_reused"] is False
    assert len(binding["files"]) == 4
    assert {
        "FreshOutcomeArtifactWriter.write_raw",
        "FreshOutcomeArtifactWriter.write_result",
        "AuthoritativeTerminalDispatcher.dispatch",
        "FreshOutcomeIntegratedExecutionKernel.complete_job",
    } <= {item["symbol"] for item in binding["symbols"]}
    assert report.integration_contract_id == contract["contract_id"]


def test_all_16_reachable_terminals_use_actual_invoke_and_fresh_artifacts(
    built: tuple[Path, models.RepairPreflightReport],
) -> None:
    output, report = built
    audit = _load(output / "production_terminal_integration_audit.json")
    controls = audit["controls"]
    assert len(controls) == 16
    assert {item["target_terminal_kind"] for item in controls} == set(preflight.REACHABLE_TERMINALS)
    assert len({item["exact_job_id"] for item in controls}) == 16
    assert audit["v194_invoke_count"] == 16
    assert audit["dispatcher_decision_count"] == 16
    assert audit["terminal_projection_count"] == 16
    assert audit["fresh_raw_count"] == audit["fresh_result_count"] == 16
    assert audit["reconstructed_trace_count"] == 16
    assert audit["reconstructed_outcome_count"] == 16
    assert audit["raw_result_actual_byte_match_count"] == 32
    assert audit["old_fixture_complete_count"] == 0
    assert audit["exception_escape_count"] == 0
    assert audit["provider_calls"] == 0
    assert len(tuple((output / "raw").glob("*.json"))) == 16
    assert len(tuple((output / "result").glob("*.json"))) == 16
    assert all(item["raw_before_result"] for item in controls)
    assert all(not item["caller_supplied_terminal"] for item in controls)
    assert all(item["target_terminal_kind"] == item["observed_terminal_kind"] for item in controls)
    assert report.production_terminal_integration_success_count == 16


def test_two_excluded_terminals_have_dispatcher_specific_witnesses(
    built: tuple[Path, models.RepairPreflightReport],
) -> None:
    output, report = built
    audit = _load(output / "dispatcher_exclusion_audit.json")
    assert {item["terminal_kind"] for item in audit["witnesses"]} == {
        "measurement_support_exit",
        "policy_horizon_exhausted",
    }
    assert audit["exact_witness_count"] == audit["exclusion_pass_count"] == 2
    assert audit["empirical_denominator_entry_count"] == 0
    assert all(item["dispatcher_branch_token_count"] == 0 for item in audit["witnesses"])
    assert all(item["runner_branch_token_count"] == 0 for item in audit["witnesses"])
    assert all(item["caller_terminal_parameter_count"] == 0 for item in audit["witnesses"])
    assert report.excluded_terminal_witness_count == 2


def test_external_authorization_rejects_before_credentials_or_client(
    built: tuple[Path, models.RepairPreflightReport],
) -> None:
    output, report = built
    audit = _load(output / "authorization_ingress_audit.json")
    controls = {item["control_name"]: item for item in audit["controls"]}
    assert controls["legal_preflight_parent"]["admitted"] is True
    assert controls["legal_preflight_parent"]["client_construction_count"] == 1
    for name in (
        "missing_parent",
        "modified_parent",
        "self_declared_parent",
        "cross_experiment_parent",
        "legal_parent_provider_request",
    ):
        assert controls[name]["rejected"] is True
        assert controls[name]["credential_lookup_count"] == 0
        assert controls[name]["client_construction_count"] == 0
    assert audit["gate_passed"] is True
    assert report.external_authorization_ingress_passed is True
    assert report.provider_calls == 0


def test_destructive_controls_and_transition_remain_fail_closed(
    built: tuple[Path, models.RepairPreflightReport],
) -> None:
    output, report = built
    destructive = _load(output / "destructive_audit.json")
    transition = _load(output / "prospective_transition.json")
    static = _load(output / "static_audit.json")
    names = {item["attack_name"] for item in destructive["attacks"]}
    assert destructive["attack_count"] == destructive["rejection_count"] == 13
    assert destructive["accepted_count"] == 0
    assert destructive["fully_rehashed_attack_count"] >= 4
    assert {
        "caller_supplied_terminal_argument",
        "duplicate_complete_job",
        "rehashed_decision_terminal_crossing",
        "rehashed_integration_contract_crossing",
        "excluded_terminal_injection",
        "result_before_raw",
        "old_fixture_complete_payload",
    } <= names
    assert static["passed_count"] == static["gate_count"] == 28
    assert static["failed_count"] == 0
    assert transition["next_stage"] == models.NEXT_STAGE
    assert transition["online_execution_authorized"] is False
    assert transition["provider_calls_authorized"] is False
    assert transition["six_outcome_contract_semantic_change_authorized"] is False
    assert transition["qa_change_authorized"] is False
    assert report.online_development_execution_authorized is False
    assert report.empirical_rows == report.empirical_estimates == 0


def test_second_complete_build_is_byte_identical(
    built: tuple[Path, models.RepairPreflightReport],
    tmp_path: Path,
) -> None:
    first, _ = built
    second = tmp_path / "second"
    preflight.build(
        repository_root=REPOSITORY_ROOT,
        audit_path=AUDIT_PATH,
        output_dir=second,
    )
    expected = {
        path.relative_to(first).as_posix(): path.read_bytes()
        for path in first.rglob("*")
        if path.is_file()
    }
    observed = {
        path.relative_to(second).as_posix(): path.read_bytes()
        for path in second.rglob("*")
        if path.is_file()
    }
    assert observed == expected


def test_existing_output_is_not_replaced(tmp_path: Path) -> None:
    output = tmp_path / "existing"
    output.mkdir()
    sentinel = output / "sentinel.txt"
    sentinel.write_text("keep", encoding="utf-8")
    with pytest.raises(preflight.RepairPreflightError):
        preflight.build(
            repository_root=REPOSITORY_ROOT,
            audit_path=AUDIT_PATH,
            output_dir=output,
        )
    assert sentinel.read_text(encoding="utf-8") == "keep"
