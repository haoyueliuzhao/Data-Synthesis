from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest

from trusted_synthesis.experiments.vtdo_experiment import (
    phase1_v26_fresh_artifact_backed_terminal_to_outcome_online_authorization as authorization,
)
from trusted_synthesis.experiments.vtdo_experiment import (
    phase1_v26_fresh_artifact_backed_terminal_to_outcome_online_authorization_models as models,
)

PACKAGE_ROOT = Path(__file__).resolve().parents[1]
REPOSITORY_ROOT = PACKAGE_ROOT.parent
EXTERNAL_AUDIT = Path(
    "/home/zhuxinrui/.codex/attachments/26338871-a2ff-4e4a-924c-751372f2a1af/pasted-text.txt"
)


def _load(path: Path) -> Any:
    return json.loads(path.read_bytes())


@pytest.fixture(scope="module")
def built(
    tmp_path_factory: pytest.TempPathFactory,
) -> tuple[Path, models.OnlineAuthorizationReport]:
    output = tmp_path_factory.mktemp("v26-199") / "formal"
    report = authorization.build(
        repository_root=REPOSITORY_ROOT,
        audit_path=EXTERNAL_AUDIT,
        output_dir=output,
    )
    return output, report


def test_exact_external_decision_and_v198_authority_freeze(
    built: tuple[Path, models.OnlineAuthorizationReport],
) -> None:
    output, report = built
    external = _load(output / "external_online_authorization_decision.json")
    freeze = _load(output / "v26_198_authority_freeze_audit.json")
    assert external["audit_sha256"] == authorization.EXPECTED_EXTERNAL_AUDIT_SHA256
    assert external["audit_byte_count"] == authorization.EXPECTED_EXTERNAL_AUDIT_BYTES
    assert external["consumed_stage"] == models.CONSUMED_STAGE
    assert external["issue_narrow_online_authorization"] is True
    assert freeze["v198_report_id"] == authorization.V198_REPORT_ID
    assert freeze["v198_decision_id"] == authorization.V198_DECISION_ID
    assert freeze["v198_transition_id"] == authorization.V198_TRANSITION_ID
    assert freeze["formal_file_count"] == freeze["formal_file_match_count"] == 48
    assert freeze["formal_total_byte_count"] == 275_894
    assert freeze["online_execution_authorized_before_v199"] is False
    assert report.v198_formal_file_match_count == 48


def test_exact_frozen_condition_and_generation_profile(
    built: tuple[Path, models.OnlineAuthorizationReport],
) -> None:
    output, report = built
    condition = _load(output / "frozen_execution_condition_binding.json")
    assert condition["package_catalog_id"] == authorization.PACKAGE_CATALOG_ID
    assert condition["manifest_id"] == authorization.MANIFEST_ID
    assert condition["runner_id"] == authorization.RUNNER_ID
    assert condition["execution_contract_id"] == authorization.EXECUTION_CONTRACT_ID
    assert condition["generation_profile_id"] == authorization.GENERATION_PROFILE_ID
    assert condition["model_config_id"] == authorization.MODEL_CONFIG_ID
    assert condition["thinking_policy_id"] == authorization.THINKING_POLICY_ID
    assert condition["exact_package_count"] == report.exact_package_count == 32
    assert condition["exact_job_count"] == report.exact_job_count == 192
    assert condition["exact_registered_invocation_count"] == 792
    assert len(condition["exact_job_ids"]) == len(set(condition["exact_job_ids"])) == 192
    assert condition["unique_raw_namespace_count"] == 192
    assert condition["unique_result_namespace_count"] == 192
    assert len(condition["parent_files"]) == 9
    assert condition["condition_changed"] is False


def test_successor_integration_authority_is_exact_and_old_fallback_is_forbidden(
    built: tuple[Path, models.OnlineAuthorizationReport],
) -> None:
    output, _report = built
    successor = _load(output / "successor_integration_authority_binding.json")
    assert successor["v197_report_id"] == authorization.V197_REPORT_ID
    assert successor["integration_contract_id"] == authorization.V197_INTEGRATION_CONTRACT_ID
    assert (
        successor["integration_implementation_binding_id"]
        == authorization.V197_IMPLEMENTATION_BINDING_ID
    )
    authority_ids = {
        successor["terminal_registry_id"],
        successor["raw_descriptor_contract_id"],
        successor["result_descriptor_contract_id"],
        successor["attempt_trace_contract_id"],
        successor["outcome_row_contract_id"],
        successor["evaluator_contract_id"],
    }
    assert len(authority_ids) == 6
    assert len(successor["successor_files"]) == 4
    assert successor["old_complete_job_fallback_forbidden"] is True
    assert successor["fresh_writer_required"] is True
    assert successor["raw_before_result_required"] is True
    assert successor["caller_terminal_forbidden"] is True


def test_authorization_is_narrow_unique_and_not_consumed(
    built: tuple[Path, models.OnlineAuthorizationReport],
) -> None:
    output, report = built
    exact = _load(output / "exact_online_execution_authorization.json")
    transition = _load(output / "prospective_transition.json")
    assert exact["authorized_stage"] == models.NEXT_STAGE
    assert exact["online_execution_authorized"] is True
    assert exact["provider_calls_authorized"] is True
    assert exact["exact_192_job_execution_authorized"] is True
    assert exact["maximum_manifest_executions"] == 1
    assert exact["authorization_reuse_authorized"] is False
    assert exact["replacement_rerun_authorized"] is False
    assert exact["recovery_execution_authorized"] is False
    assert exact["source_or_manifest_change_authorized"] is False
    assert exact["qa_integration_authorized"] is False
    assert exact["provider_calls_during_authorization"] == 0
    assert transition["next_stage"] == models.NEXT_STAGE
    assert transition["authorization_consumed"] is False
    assert transition["provider_calls_executed"] == 0
    assert report.online_authorization_issued is True
    assert report.online_authorization_consumed is False


def test_precredential_guard_rejects_all_invalid_requests_before_factories(
    built: tuple[Path, models.OnlineAuthorizationReport],
) -> None:
    output, _report = built
    audit = _load(output / "precredential_admission_audit.json")
    controls = {item["control_name"]: item for item in audit["controls"]}
    assert len(controls) == 10
    legal = controls.pop("exact_online_authorization")
    assert legal["admitted"] is True
    assert (
        legal["client_factory_count"],
        legal["kernel_writer_factory_count"],
        legal["outcome_writer_factory_count"],
    ) == (1, 1, 1)
    assert len(controls) == 9
    for control in controls.values():
        assert control["rejected"] is True
        assert control["rejection_reason_sha256"] is not None
        assert control["client_factory_count"] == 0
        assert control["kernel_writer_factory_count"] == 0
        assert control["outcome_writer_factory_count"] == 0
        assert control["credential_lookup_count"] == 0
        assert control["provider_calls"] == 0
    assert audit["invalid_control_factory_call_count"] == 0
    assert audit["credential_lookup_count"] == 0


def test_destructive_controls_and_scope_exclusions_are_noncompensatory(
    built: tuple[Path, models.OnlineAuthorizationReport],
) -> None:
    output, report = built
    destructive = _load(output / "destructive_audit.json")
    scope = _load(output / "scope_exclusion_audit.json")
    static = _load(output / "static_audit.json")
    assert destructive["control_count"] == destructive["rejected_count"] == 20
    assert destructive["accepted_count"] == 0
    assert len({item["attack_name"] for item in destructive["controls"]}) == 20
    assert all(item["downstream_rehash_completed"] for item in destructive["controls"])
    assert all(item["rejected_before_client_factory"] for item in destructive["controls"])
    zero_fields = (
        "manifest_job_execution_count",
        "provider_calls",
        "credential_lookups",
        "raw_files_written",
        "result_files_written",
        "development_outcomes",
        "empirical_rows",
        "empirical_estimates",
        "qa_population_reads",
        "qa_change_count",
        "mapper_rows",
        "state_rows",
        "frequency_rows",
        "contribution_rows",
        "vtdo_rows",
        "old_complete_job_calls",
    )
    assert all(scope[field] == 0 for field in zero_fields)
    assert static["passed_count"] == static["gate_count"] == 28
    assert static["failed_count"] == 0
    assert report.provider_calls == 0
    assert report.development_outcomes == 0


def test_formal_directory_rebuild_is_byte_identical(
    built: tuple[Path, models.OnlineAuthorizationReport],
    tmp_path: Path,
) -> None:
    first, _report = built
    second = tmp_path / "second"
    authorization.build(
        repository_root=REPOSITORY_ROOT,
        audit_path=EXTERNAL_AUDIT,
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
    assert len(expected) == 16
    assert observed == expected
    assert _load(first / "sealed_evidence_manifest.json")["file_count"] == 13
    assert _load(first / "artifact_manifest.json")["file_count"] == 15


def test_existing_output_is_not_replaced(tmp_path: Path) -> None:
    output = tmp_path / "existing"
    output.mkdir()
    sentinel = output / "sentinel.txt"
    sentinel.write_text("keep", encoding="utf-8")
    with pytest.raises(authorization.OnlineAuthorizationError):
        authorization.build(
            repository_root=REPOSITORY_ROOT,
            audit_path=EXTERNAL_AUDIT,
            output_dir=output,
        )
    assert sentinel.read_text(encoding="utf-8") == "keep"
