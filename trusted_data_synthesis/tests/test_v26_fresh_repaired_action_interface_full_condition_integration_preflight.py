# ruff: noqa: E501
from __future__ import annotations

import hashlib
import inspect
import json
from pathlib import Path
from typing import Any

import pytest

from trusted_synthesis.experiments.vtdo_experiment import (
    phase1_v26_fresh_repaired_action_interface_full_condition_integration_preflight as experiment,
)
from trusted_synthesis.experiments.vtdo_experiment import (
    phase1_v26_fresh_repaired_action_interface_full_condition_integration_preflight_models as models,
)

PACKAGE_ROOT = Path(__file__).resolve().parents[1]
REPOSITORY_ROOT = PACKAGE_ROOT.parent
FORMAL_ROOT = PACKAGE_ROOT / experiment.OUTPUT_DIR
AUDIT_PATH = FORMAL_ROOT / "external_audit.txt"


def _load(path: Path) -> Any:
    return json.loads(path.read_bytes())


@pytest.fixture(scope="module")
def rebuilt(tmp_path_factory: pytest.TempPathFactory) -> Path:
    source = _load(FORMAL_ROOT / "source_identity.json")
    target = tmp_path_factory.mktemp("v26-206") / "preflight"
    experiment.build(
        repository_root=REPOSITORY_ROOT,
        output_dir=target,
        external_audit_path=AUDIT_PATH,
        source_identity=(source["source_commit"], source["source_tree"]),
    )
    return target


def test_external_authorization_and_predecessor_freeze_are_exact() -> None:
    authorization = models.ExternalPreflightAuthorization.model_validate(
        _load(FORMAL_ROOT / "external_authorization.json")
    )
    freeze = models.PredecessorFreeze.model_validate(_load(FORMAL_ROOT / "predecessor_freeze.json"))
    assert authorization.audit_sha256 == experiment.EXTERNAL_AUDIT_SHA256
    assert authorization.audit_byte_count == experiment.EXTERNAL_AUDIT_BYTES
    assert authorization.only_authorized_successor == models.CONSUMED_STAGE
    assert authorization.provider_calls_authorized == 0
    assert authorization.credential_lookups_authorized == 0
    assert authorization.full_repaired_192_job_execution_authorized is False
    assert freeze.v205_formal_file_count == 14
    assert freeze.v205_formal_byte_count == 91_230
    assert freeze.v205_manifest_member_match_count == 13
    assert freeze.v194_package_catalog_id == experiment.V194_PACKAGE_CATALOG_ID
    assert freeze.v194_manifest_id == experiment.V194_MANIFEST_ID
    assert freeze.v194_runner_id == experiment.V194_RUNNER_ID
    assert freeze.v194_execution_contract_id == experiment.V194_EXECUTION_CONTRACT_ID
    assert freeze.v193_prompt_evidence_set_id == experiment.V193_EVIDENCE_SET_ID
    assert freeze.v203_action_contract_id == experiment.V203_ACTION_CONTRACT_ID


def test_fresh_full_condition_identity_chain_is_exact_and_disjoint() -> None:
    profile = models.FullConditionRepairProfile.model_validate(
        _load(FORMAL_ROOT / "full_condition_repair_profile.json")
    )
    catalog = models.RepairedRunnerPackageCatalog.model_validate(
        _load(FORMAL_ROOT / "repaired_runner_package_catalog.json")
    )
    manifest = models.RepairedDevelopmentManifest.model_validate(
        _load(FORMAL_ROOT / "repaired_development_manifest.json")
    )
    runner = models.RepairedRunnerContract.model_validate(
        _load(FORMAL_ROOT / "repaired_runner_contract.json")
    )
    execution = models.RepairedExecutionContract.model_validate(
        _load(FORMAL_ROOT / "repaired_execution_contract.json")
    )
    assert profile.exact_required_fields == (
        "state_id",
        "action_id",
        "decision_kind",
        "protocol",
    )
    assert profile.exact_allowed_fields == profile.exact_required_fields
    assert profile.grammar_id_host_side_only is True
    assert profile.answer_and_operation_schemas_verifier_metadata_only is True
    assert profile.parser_relaxation is False
    assert profile.historical_payload_adaptation is False
    assert len(catalog.packages) == 32
    assert len(manifest.jobs) == 192
    assert len({(item.package_id, item.replica_index) for item in manifest.jobs}) == 192
    assert len({item.raw_namespace for item in manifest.jobs}) == 192
    assert len({item.result_namespace for item in manifest.jobs}) == 192
    assert len({item.trace_namespace for item in manifest.jobs}) == 192
    assert len({item.outcome_namespace for item in manifest.jobs}) == 192
    assert runner.manifest_id == execution.manifest_id == manifest.manifest_id
    assert execution.maximum_primary_requests == 21
    assert execution.maximum_provider_calls == 23
    assert execution.maximum_transport_invocations == 24
    assert execution.maximum_rollout_tokens == 1_120_000
    assert execution.maximum_prompt_utf8_bytes == 60_000
    assert execution.online_execution_authorized is False


def test_all_action_and_final_callsites_are_bound_and_total() -> None:
    census = models.RepairedCallsiteCensus.model_validate(
        _load(FORMAL_ROOT / "repaired_callsite_census.json")
    )
    assert len(census.rows) == 792
    assert census.first_action_count == 192
    assert census.subsequent_action_count == 288
    assert census.correction_count == 120
    assert census.final_count == 192
    assert census.action_contract_compile_count == 600
    assert census.final_grammar_binding_count == 192
    assert census.maximum_repaired_message_byte_count <= 60_000
    assert census.parser_relaxation_count == 0
    assert census.historical_adaptation_count == 0
    action_rows = [item for item in census.rows if item.phase != "final"]
    correction_rows = [item for item in census.rows if item.phase == "correction"]
    final_rows = [item for item in census.rows if item.phase == "final"]
    assert len(action_rows) == 600
    assert len(correction_rows) == 120
    assert len(final_rows) == 192
    assert all(item.exact_four_field_action_contract for item in action_rows)
    assert all(item.candidate_action_ids for item in action_rows)
    assert all(item.action_grammar_id_model_visible_count == 0 for item in action_rows)
    assert all(item.old_response_abi_model_visible_count == 0 for item in action_rows)
    assert all(item.rejection_receipt_id for item in correction_rows)
    assert all(not item.exact_four_field_action_contract for item in final_rows)
    assert len({item.repaired_prompt_id for item in census.rows}) == 792
    assert len({item.request_id for item in census.rows}) == 792


def test_scripted_action_state_correction_final_and_outcome_chain_close() -> None:
    audit = models.ScriptedIntegrationAudit.model_validate(
        _load(FORMAL_ROOT / "scripted_integration_audit.json")
    )
    assert len(audit.rows) == 192
    assert audit.first_action_parse_count == 192
    assert audit.subsequent_action_parse_count == 288
    assert audit.typed_rejection_branch_count == 120
    assert audit.correction_parse_count == 120
    assert audit.final_parse_count == 192
    assert audit.terminal_state_count == 192
    assert audit.independent_validity_count == 192
    assert audit.scripted_qualified_count == 192
    assert audit.scripted_raw_count == 192
    assert audit.scripted_result_count == 192
    assert audit.scripted_trace_count == 192
    assert audit.scripted_outcome_count == 192
    assert audit.unique_layer_identity_count == 768
    assert audit.exception_escape_count == 0
    assert audit.empirical_row_count == 0
    assert all(item.raw_result_trace_outcome_parent_closure for item in audit.rows)
    assert all(not item.empirical for item in audit.rows)


def test_required_failure_controls_terminalize_without_escape() -> None:
    audit = models.FailureControlAudit.model_validate(
        _load(FORMAL_ROOT / "failure_control_audit.json")
    )
    assert audit.control_count == 5
    assert audit.typed_outcome_count == 5
    assert audit.exception_escape_count == 0
    assert audit.accepted_control_count == 0
    assert {item.control_name for item in audit.controls} == {
        "invalid_first_action_abi",
        "unknown_action_reference",
        "invalid_correction_abi",
        "invalid_final_abi",
        "typed_outer_terminal",
    }
    assert all(item.expected_terminal == item.observed_terminal for item in audit.controls)
    assert all(item.typed_outcome_count == 1 for item in audit.controls)


def test_estimands_f0_f5_and_transition_preserve_boundary() -> None:
    estimand = models.ProspectiveEstimandContract.model_validate(
        _load(FORMAL_ROOT / "prospective_estimand_contract.json")
    )
    gates = models.FullConditionGateAudit.model_validate(
        _load(FORMAL_ROOT / "full_condition_gate_audit.json")
    )
    transition = models.ProspectiveTransition.model_validate(
        _load(FORMAL_ROOT / "prospective_transition.json")
    )
    report = models.PreflightReport.model_validate(_load(FORMAL_ROOT / "report.json"))
    assert estimand.exact_denominator == 192
    assert estimand.pre_action_abi_terminal_counts_as_false is True
    assert estimand.outer_terminal_remains_in_denominator is True
    assert estimand.post_action_abi_conditional_null_when_denominator_zero is True
    assert estimand.q_first_numerator is None
    assert estimand.q_bounded_correction_numerator is None
    assert estimand.q_first_estimate is None
    assert estimand.q_bounded_correction_estimate is None
    assert estimand.confidence_intervals is None
    assert gates.all_gates_passed is True
    assert all(
        getattr(gates, name)
        for name in (
            "f0_authority_and_predecessor_freeze_passed",
            "f1_exact_source_equality_and_fresh_identity_disjointness_passed",
            "f2_repaired_action_interface_callsite_totality_passed",
            "f3_scripted_action_state_correction_final_closure_passed",
            "f4_raw_result_trace_outcome_parent_closure_passed",
            "f5_zero_provider_credential_qa_mapper_vtdo_passed",
        )
    )
    assert gates.provider_calls == gates.credential_lookups == 0
    assert gates.capability_estimate is None
    assert transition.next_stage == models.NEXT_STAGE
    assert transition.provider_calls_authorized == 0
    assert transition.full_repaired_192_job_execution_authorized is False
    assert transition.parser_relaxation_authorized is False
    assert report.development_model_outcomes == 0
    assert report.empirical_rows == report.empirical_estimates == 0


def test_formal_manifest_and_empty_rebuild_are_byte_exact(rebuilt: Path) -> None:
    artifact = models.ArtifactManifest.model_validate(_load(FORMAL_ROOT / "artifact_manifest.json"))
    actual_files = tuple(sorted(path for path in FORMAL_ROOT.rglob("*") if path.is_file()))
    assert artifact.file_count == 16
    assert len(actual_files) == 17
    assert {item.relative_path for item in artifact.members} == {
        path.relative_to(FORMAL_ROOT).as_posix()
        for path in actual_files
        if path.name != "artifact_manifest.json"
    }
    for member in artifact.members:
        path = FORMAL_ROOT / member.relative_path
        assert path.stat().st_size == member.byte_count
        assert hashlib.sha256(path.read_bytes()).hexdigest() == member.sha256
    rebuilt_files = tuple(sorted(path for path in rebuilt.rglob("*") if path.is_file()))
    assert {path.relative_to(rebuilt).as_posix() for path in rebuilt_files} == {
        path.relative_to(FORMAL_ROOT).as_posix() for path in actual_files
    }
    for rebuilt_path in rebuilt_files:
        formal_path = FORMAL_ROOT / rebuilt_path.relative_to(rebuilt)
        assert rebuilt_path.read_bytes() == formal_path.read_bytes()


def test_source_has_no_provider_or_credential_ingress() -> None:
    source = inspect.getsource(experiment)
    assert "DEEPSEEK_API_KEY" not in source
    assert "client_factory" not in source
    assert "credential_loader" not in source
    assert "complete_json_certified" not in source
    assert "provider_call_made" not in source
