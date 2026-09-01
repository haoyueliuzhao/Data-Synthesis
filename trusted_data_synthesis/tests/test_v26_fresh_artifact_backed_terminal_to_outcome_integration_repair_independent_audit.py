from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest

from trusted_synthesis.experiments.vtdo_experiment import (
    phase1_v26_fresh_artifact_backed_terminal_to_outcome_integration_repair_independent_audit as audit,  # noqa: E501
)
from trusted_synthesis.experiments.vtdo_experiment import (
    phase1_v26_fresh_artifact_backed_terminal_to_outcome_integration_repair_independent_audit_models as models,  # noqa: E501
)

PACKAGE_ROOT = Path(__file__).resolve().parents[1]
REPOSITORY_ROOT = PACKAGE_ROOT.parent
EXTERNAL_AUDIT = Path(
    "/home/zhuxinrui/.codex/attachments/27e0447a-62bb-4d2a-9beb-9daee0099c04/pasted-text.txt"
)


def _load(path: Path) -> Any:
    return json.loads(path.read_bytes())


@pytest.fixture(scope="module")
def built(
    tmp_path_factory: pytest.TempPathFactory,
) -> tuple[Path, models.IndependentAuditReport]:
    output = tmp_path_factory.mktemp("v26-198") / "formal"
    report = audit.build(
        repository_root=REPOSITORY_ROOT,
        audit_path=EXTERNAL_AUDIT,
        output_dir=output,
    )
    return output, report


def test_exact_external_parent_and_v197_freeze(
    built: tuple[Path, models.IndependentAuditReport],
) -> None:
    output, report = built
    authorization = _load(output / "external_independent_audit_authorization.json")
    freeze = _load(output / "v26_197_source_and_artifact_freeze_audit.json")
    assert authorization["audit_sha256"] == audit.EXPECTED_EXTERNAL_AUDIT_SHA256
    assert authorization["audit_byte_count"] == audit.EXPECTED_EXTERNAL_AUDIT_BYTES
    assert freeze["v197_report_id"] == audit.V197_REPORT_ID
    assert freeze["v197_transition_id"] == audit.V197_TRANSITION_ID
    assert freeze["v197_source_commit"] == audit.AUDITED_SOURCE_COMMIT
    assert freeze["v197_source_tree"] == audit.AUDITED_SOURCE_TREE
    assert freeze["formal_file_count"] == freeze["formal_file_match_count"] == 48
    assert freeze["formal_total_byte_count"] == 285_781
    assert freeze["six_authority_identity_match_count"] == 6
    assert report.v197_formal_file_match_count == 48


def test_detached_checkout_rebuilds_all_48_files_byte_for_byte(
    built: tuple[Path, models.IndependentAuditReport],
) -> None:
    output, report = built
    rebuild = _load(output / "v26_197_formal_rebuild_audit.json")
    assert rebuild["detached_source_commit"] == audit.AUDITED_SOURCE_COMMIT
    assert rebuild["detached_source_tree"] == audit.AUDITED_SOURCE_TREE
    assert rebuild["frozen_file_count"] == rebuild["rebuilt_file_count"] == 48
    assert rebuild["path_match_count"] == 48
    assert rebuild["sha256_match_count"] == 48
    assert rebuild["byte_count_match_count"] == 48
    assert rebuild["actual_byte_match_count"] == 48
    assert rebuild["candidate_report_used_as_outcome_oracle"] is False
    assert rebuild["credential_environment_variable_count"] == 0
    assert report.v197_formal_rebuild_byte_match_count == 48


def test_16_actual_paths_are_independently_reconstructed_from_bytes(
    built: tuple[Path, models.IndependentAuditReport],
) -> None:
    output, report = built
    replay = _load(output / "independent_terminal_runtime_replay_audit.json")
    controls = replay["controls"]
    assert len(controls) == 16
    assert len({item["exact_job_id"] for item in controls}) == 16
    assert {item["observed_terminal_kind"] for item in controls} == set(audit.REACHABLE_TERMINALS)
    assert replay["actual_invoke_count"] == 16
    assert replay["fresh_raw_count"] == replay["fresh_result_count"] == 16
    assert replay["actual_raw_result_byte_match_count"] == 32
    assert replay["candidate_raw_result_byte_match_count"] == 32
    assert replay["independent_terminal_reconstruction_count"] == 16
    assert replay["independent_failure_locus_reconstruction_count"] == 16
    assert replay["independent_trace_reconstruction_count"] == 16
    assert replay["independent_outcome_reconstruction_count"] == 16
    assert replay["old_complete_job_call_count"] == 0
    assert replay["provider_calls"] == 0
    assert len(tuple((output / "raw").glob("*.json"))) == 16
    assert len(tuple((output / "result").glob("*.json"))) == 16
    assert all(
        item["expected_terminal_kind"] == item["observed_terminal_kind"] for item in controls
    )
    assert all(item["terminal_value_entered_harness_input"] is False for item in controls)
    assert report.independent_terminal_replay_count == 16
    assert report.independent_raw_result_byte_match_count == 32


def test_dispatcher_real_codomain_excludes_two_not_applicable_terminals(
    built: tuple[Path, models.IndependentAuditReport],
) -> None:
    output, report = built
    codomain = _load(output / "dispatcher_codomain_audit.json")
    reachable = set(codomain["registry_reachable_terminals"])
    assert reachable == set(codomain["dispatcher_literal_outputs"])
    assert reachable == set(codomain["actual_replay_outputs"])
    assert set(codomain["excluded_terminals"]) == set(audit.EXCLUDED_TERMINALS)
    assert not reachable & set(codomain["excluded_terminals"])
    assert codomain["excluded_dispatcher_output_count"] == 0
    assert codomain["excluded_actual_output_count"] == 0
    assert codomain["string_token_only_witness"] is False
    assert report.dispatcher_codomains_match is True


def test_terminal_injection_and_authorization_ordering_fail_closed(
    built: tuple[Path, models.IndependentAuditReport],
) -> None:
    output, report = built
    injection = _load(output / "terminal_injection_audit.json")
    ordering = _load(output / "authorization_ordering_audit.json")
    assert injection["invoke_terminal_parameter_count"] == 0
    assert injection["complete_job_terminal_parameter_count"] == 0
    assert injection["client_plan_terminal_field_count"] == 0
    assert injection["caller_supplied_terminal_rejection_count"] == 1
    controls = {item["control_name"]: item for item in ordering["controls"]}
    assert controls["legal_preflight_parent"]["admitted"] is True
    for name, control in controls.items():
        if name == "legal_preflight_parent":
            assert control["client_factory_count"] == 1
            assert control["kernel_writer_factory_count"] == 1
            assert control["outcome_writer_factory_count"] == 1
        else:
            assert control["rejected"] is True
            assert control["client_factory_count"] == 0
            assert control["kernel_writer_factory_count"] == 0
            assert control["outcome_writer_factory_count"] == 0
        assert control["credential_lookup_count"] == 0
    assert ordering["invalid_control_factory_call_count"] == 0
    assert report.terminal_injection_count == 0
    assert report.invalid_authorization_factory_call_count == 0


def test_legacy_completion_has_no_successor_runtime_bypass(
    built: tuple[Path, models.IndependentAuditReport],
) -> None:
    output, report = built
    bypass = _load(output / "legacy_completion_bypass_audit.json")
    transition = _load(output / "prospective_transition.json")
    static = _load(output / "static_audit.json")
    assert bypass["old_fixture_complete_source_present"] is True
    assert bypass["successor_calls_old_complete_job_count"] == 0
    assert bypass["old_complete_job_runtime_call_count"] == 0
    assert bypass["successor_fresh_writer_runtime_call_count"] == 32
    assert bypass["future_online_entry_materialized"] is False
    assert transition["next_stage"] == models.NEXT_STAGE
    assert transition["online_execution_authorized"] is False
    assert transition["provider_calls_authorized"] is False
    assert transition["job_192_execution_authorized"] is False
    assert static["passed_count"] == static["gate_count"] == 30
    assert static["failed_count"] == 0
    assert report.old_complete_job_runtime_call_count == 0
    assert report.online_execution_authorized is False


def test_formal_directory_rebuild_is_byte_identical(
    built: tuple[Path, models.IndependentAuditReport],
    tmp_path: Path,
) -> None:
    first, _report = built
    second = tmp_path / "second"
    audit.build(
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
    assert len(expected) == 48
    assert observed == expected


def test_existing_output_is_not_replaced(tmp_path: Path) -> None:
    output = tmp_path / "existing"
    output.mkdir()
    sentinel = output / "sentinel.txt"
    sentinel.write_text("keep", encoding="utf-8")
    with pytest.raises(audit.IndependentAuditError):
        audit.build(
            repository_root=REPOSITORY_ROOT,
            audit_path=EXTERNAL_AUDIT,
            output_dir=output,
        )
    assert sentinel.read_text(encoding="utf-8") == "keep"
