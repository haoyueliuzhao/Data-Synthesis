# ruff: noqa: E501
from __future__ import annotations

import ast
import hashlib
import inspect
import json
import os
import subprocess
from collections import Counter
from pathlib import Path
from typing import Any

import pytest

from trusted_synthesis.experiments.vtdo_experiment import (
    phase1_v26_fresh_exact_v209_unbound_provider_failure_recovery_population_independent_audit as subject,
)
from trusted_synthesis.experiments.vtdo_experiment import (
    phase1_v26_fresh_exact_v209_unbound_provider_failure_recovery_population_independent_audit_models as models,
)

ROOT = Path(__file__).resolve().parents[2]
ATTACHED_REVIEW = Path(
    "/home/zhuxinrui/.codex/attachments/7c0137df-b863-4bff-954d-5150cab4a15d/pasted-text.txt"
)


def _formal_dir() -> Path:
    direct = ROOT / subject.OUTPUT_DIR
    nested = ROOT / "trusted_data_synthesis" / subject.OUTPUT_DIR
    return direct if direct.is_dir() or not nested.is_dir() else nested


def _review_path() -> Path:
    explicit = os.environ.get("V26_230_EXTERNAL_REVIEW")
    formal = _formal_dir() / "external_review.txt"
    path = Path(explicit) if explicit else (formal if formal.is_file() else ATTACHED_REVIEW)
    if not path.is_file():
        pytest.skip("exact v26.230 external review is unavailable")
    return path


def _load(root: Path, relative_path: str) -> dict[str, Any]:
    value = json.loads((root / relative_path).read_bytes())
    assert isinstance(value, dict)
    return value


def _files(root: Path) -> dict[str, bytes]:
    return {
        path.relative_to(root).as_posix(): path.read_bytes()
        for path in root.rglob("*")
        if path.is_file()
    }


@pytest.fixture(scope="module")
def built(tmp_path_factory: pytest.TempPathFactory) -> Path:
    formal = _formal_dir()
    if formal.is_dir() and (formal / "source_identity.json").is_file():
        source = _load(formal, "source_identity.json")
        source_identity = (str(source["source_commit"]), str(source["source_tree"]))
    else:
        commit = os.environ.get("V26_230_TEST_SOURCE_COMMIT")
        if commit is None:
            commit = subprocess.run(
                ("git", "rev-parse", "HEAD"),
                cwd=ROOT,
                check=True,
                capture_output=True,
                text=True,
            ).stdout.strip()
        tree = subprocess.run(
            ("git", "rev-parse", f"{commit}^{{tree}}"),
            cwd=ROOT,
            check=True,
            capture_output=True,
            text=True,
        ).stdout.strip()
        source_identity = (commit, tree)
    output = tmp_path_factory.mktemp("v26-230") / "formal"
    subject.build(
        repository_root=ROOT,
        output_dir=output,
        external_review_path=_review_path(),
        source_identity=source_identity,
    )
    return output


def test_exact_external_review_and_v229_freeze(built: Path) -> None:
    authorization = models.ExternalAuthorization.model_validate(
        _load(built, "external_authorization.json")
    )
    freeze = models.V229FreezeAudit.model_validate(_load(built, "v229_freeze_audit.json"))
    review = (built / "external_review.txt").read_bytes()
    directive = (built / "operator_directive.txt").read_bytes()
    assert len(review) == authorization.external_review_byte_count == 13_653
    assert hashlib.sha256(review).hexdigest() == models.EXTERNAL_REVIEW_SHA256
    assert directive == models.OPERATOR_DIRECTIVE.encode()
    assert len(directive) == 24
    assert hashlib.sha256(directive).hexdigest() == models.OPERATOR_DIRECTIVE_SHA256
    assert freeze.source_commit == models.V229_SOURCE_COMMIT
    assert freeze.source_tree == models.V229_SOURCE_TREE
    assert (freeze.file_count, freeze.total_bytes) == (117, 1_105_367)
    assert (freeze.manifest_member_count, freeze.manifest_member_bytes) == (116, 1_088_415)
    assert freeze.manifest_id == models.V229_MANIFEST_ID
    assert freeze.artifact_root == models.V229_ARTIFACT_ROOT
    assert freeze.report_id == models.V229_REPORT_ID
    assert freeze.gate_id == models.V229_GATE_ID
    assert freeze.decision_id == models.V229_DECISION_ID
    assert freeze.transition_id == models.V229_TRANSITION_ID
    assert freeze.candidate_report_used_as_oracle is False
    assert freeze.candidate_source_rows_used_as_selector is False
    assert freeze.passed


def test_detached_rebuild_source_and_dependency_closure(built: Path) -> None:
    source = models.SourceIdentity.model_validate(_load(built, "source_identity.json"))
    implementation = models.ImplementationBinding.model_validate(
        _load(built, "implementation_binding.json")
    )
    detached = models.DetachedRebuildAudit.model_validate(
        _load(built, "detached_rebuild_audit.json")
    )
    dependencies = models.DependencyClosureAudit.model_validate(
        _load(built, "dependency_closure_audit.json")
    )
    assert source.commit_tree_relation
    assert len(source.implementation_members) == 2
    assert all(row.committed_current_bytes_match for row in source.implementation_members)
    assert implementation.candidate_helper_calls == implementation.candidate_oracle_calls == 0
    assert implementation.helper_boundary_passed
    assert detached.saved_file_count == detached.rebuilt_file_count == 117
    assert detached.actual_byte_matches == detached.path_matches == 117
    assert detached.manifest_members_revalidated == 116
    assert detached.credential_like_environment_keys == detached.provider_calls == 0
    assert dependencies.member_count == dependencies.v229_current_matches == 6
    assert dependencies.frozen_parent_matches == 2
    assert dependencies.v209_replay_blob_matches_frozen_source
    assert dependencies.v226_loader_blob_matches_frozen_source
    assert dependencies.passed


def test_independent_source_partition_and_journal(built: Path) -> None:
    partition = models.SourcePartitionAudit.model_validate(
        _load(built, "source_partition_audit.json")
    )
    journal = models.JournalAudit.model_validate(_load(built, "provider_journal_audit.json"))
    assert partition.host_ordinals == models.HOST_ORDINALS
    assert partition.provider_ordinals == models.PROVIDER_ORDINALS
    assert partition.exact_failure_count == 36
    assert partition.candidate_source_row_byte_matches == 33
    assert partition.candidate_source_authority_actual_byte_match
    assert partition.candidate_selector_calls == 0
    assert all(row.candidate_source_row_actual_byte_match for row in partition.rows)
    assert journal.provider_descriptor_count == len(journal.calls) == 88
    assert Counter(row.status for row in journal.calls) == {
        "succeeded": 55,
        "provider_error": 33,
    }
    assert journal.request_metadata_count == journal.usage_metadata_count == 88
    assert journal.response_metadata_count == 55
    assert journal.error_metadata_count == 33
    assert journal.reasoning_budget_error_count == 31
    assert journal.json_decode_error_count == 2
    assert journal.candidate_journal_actual_byte_match
    assert journal.raw_requests == journal.raw_provider_responses == 0
    assert journal.private_reasoning_bodies == 0
    assert journal.passed


def test_exact_runtime_replay_stops_before_failed_response(built: Path) -> None:
    replay = models.ReplayAudit.model_validate(_load(built, "request_replay_audit.json"))
    assert replay.exact_job_count == 33
    assert replay.reconstructed_call_count == replay.exact_request_matches == 88
    assert replay.successful_prefix_invocation_count == replay.exact_response_matches == 55
    assert replay.captured_failed_request_count == 33
    assert (
        replay.first_action_failures,
        replay.subsequent_action_failures,
        replay.final_failures,
        replay.correction_failures,
    ) == (3, 25, 5, 0)
    assert replay.failed_call_response_supplied == 0
    assert replay.failed_call_invocation_records_created == 0
    assert replay.historical_terminals_created == 0
    assert replay.candidate_replay_audit_actual_byte_match
    assert all(row.candidate_replay_row_actual_byte_match for row in replay.rows)
    assert replay.provider_calls == replay.credential_lookups == 0


def test_identifiability_partition_retains_31_2_boundary(built: Path) -> None:
    audit = models.IdentifiabilityAudit.model_validate(_load(built, "identifiability_audit.json"))
    assert audit.exact_source_count == audit.failed_requests_reconstructible == 33
    assert audit.reasoning_budget_count == 31
    assert audit.json_decode_count == 2
    assert audit.raw_response_bytes_persisted == audit.raw_response_bytes_guessed == 0
    assert audit.historical_terminals_created == 0
    reasoning = [row for row in audit.rows if row.error_type == "ReasoningBudgetExhaustedError"]
    json_rows = [row for row in audit.rows if row.error_type == "JSONDecodeError"]
    assert len(reasoning) == 31
    assert len(json_rows) == 2
    assert all(row.public_content_length == 0 for row in reasoning)
    assert all(row.public_content_sha256 == hashlib.sha256(b"").hexdigest() for row in reasoning)
    assert all(row.finish_reason == "length" for row in reasoning)
    assert all(row.failure_semantics_identifiable for row in reasoning)
    assert all(not row.failure_semantics_identifiable for row in json_rows)
    assert {row.job_ordinal for row in json_rows} == {62, 139}
    assert all(not row.exact_json_syntax_identifiable for row in audit.rows)
    assert all(row.candidate_row_actual_byte_match for row in audit.rows)
    assert audit.candidate_identifiability_audit_actual_byte_match


def test_recovery_population_is_fresh_unexecuted_and_byte_equal(built: Path) -> None:
    audit = models.RecoveryPopulationAudit.model_validate(
        _load(built, "recovery_population_audit.json")
    )
    assert audit.reconstructed_candidate_count == audit.reconstructed_recovery_job_count == 33
    assert audit.candidate_actual_byte_matches == audit.recovery_job_actual_byte_matches == 33
    assert audit.candidate_contract_actual_byte_match
    assert audit.candidate_population_actual_byte_match
    assert audit.candidate_recovery_contract_id == models.V229_RECOVERY_CONTRACT_ID
    assert audit.candidate_recovery_population_id == models.V229_RECOVERY_POPULATION_ID
    assert audit.reasoning_budget_count == 31
    assert audit.json_decode_count == 2
    assert audit.historical_identity_overlap_count == 0
    assert all(not row.historical_identity_overlap for row in audit.rows)
    assert audit.provider_calls_authorized is False
    assert audit.recovery_execution_authorized is False
    assert audit.online_authorization_created is False


def test_twelve_independent_attacks_reject_before_write_or_call(built: Path) -> None:
    audit = models.NegativeControlAudit.model_validate(_load(built, "negative_control_audit.json"))
    assert tuple(row.attack_name for row in audit.results) == models.NEGATIVE_CONTROL_NAMES
    assert audit.attack_count == audit.rejection_count == 12
    assert audit.accepted_count == 0
    assert audit.candidate_attack_helper_calls == 0
    assert audit.candidate_negative_audit_used_as_oracle is False
    assert all(row.candidate_identity_recomputed for row in audit.results)
    assert all(row.rejected for row in audit.results)
    assert all(row.writes_before_rejection == 0 for row in audit.results)
    assert all(row.provider_calls_before_rejection == 0 for row in audit.results)
    assert audit.attack_output_writes == audit.provider_calls == 0


def test_scope_gate_decision_and_transition_are_noncompensatory(built: Path) -> None:
    scope = models.ScopeBoundaryAudit.model_validate(_load(built, "scope_boundary_audit.json"))
    gate = models.GateEvaluation.model_validate(_load(built, "gate_evaluation.json"))
    decision = models.Decision.model_validate(_load(built, "decision.json"))
    transition = models.Transition.model_validate(_load(built, "transition.json"))
    report = models.Report.model_validate(_load(built, "report.json"))
    assert all(
        value == 0
        for name, value in scope.model_dump(mode="python").items()
        if name != "audit_id" and name != "passed"
    )
    assert scope.passed
    assert tuple(row.name for row in gate.gates) == models.GATE_NAMES
    assert gate.passed_count == 8
    assert gate.failed_count == 0
    assert gate.noncompensatory
    assert decision.decision == report.decision == models.DECISION_VALUE
    assert report.exact_source_count == report.fresh_recovery_job_count == 33
    assert report.reconstructed_provider_calls == 88
    assert report.successful_prefix_calls == 55
    assert report.captured_failed_requests == 33
    assert report.provider_calls == report.credential_lookups == 0
    assert report.recovery_executions == report.historical_mutations == 0
    assert report.empirical_rows == report.online_authorizations == 0
    assert transition.consumed_stage == models.CONSUMED_STAGE
    assert transition.prospective_next_stage == models.NEXT_STAGE
    assert transition.next_stage_authorized is False
    assert transition.separate_external_audit_decision_required
    assert transition.provider_calls_authorized is False
    assert transition.recovery_execution_authorized is False
    assert transition.online_authorization_created is False


def test_static_helper_boundary_excludes_v229_candidate_oracles(built: Path) -> None:
    del built
    source_path = Path(inspect.getsourcefile(subject) or "")
    tree = ast.parse(source_path.read_text())
    imported = {
        alias.name
        for node in ast.walk(tree)
        if isinstance(node, (ast.Import, ast.ImportFrom))
        for alias in node.names
    }
    assert not any(
        "unbound_provider_failure_source_authority_recovery_population_preflight" in name
        for name in imported
    )
    source = inspect.getsource(subject)
    assert "DEEPSEEK_API_KEY" not in source
    assert "load_dotenv" not in source
    assert "requests." not in source
    assert "httpx." not in source


def test_manifest_and_second_build_are_byte_identical(built: Path, tmp_path: Path) -> None:
    manifest = models.ArtifactManifest.model_validate(_load(built, "artifact_manifest.json"))
    actual = _files(built)
    assert manifest.self_excluding
    assert manifest.file_count == len(actual) - 1
    assert manifest.total_member_bytes == sum(
        len(payload)
        for relative_path, payload in actual.items()
        if relative_path != manifest.manifest_relative_path
    )
    for member in manifest.members:
        payload = actual[member.relative_path]
        assert member.sha256 == hashlib.sha256(payload).hexdigest()
        assert member.byte_count == len(payload)
    before = _files(ROOT / models.V229_DIR)
    source = models.SourceIdentity.model_validate(_load(built, "source_identity.json"))
    rebuilt = tmp_path / "empty" / "rebuilt"
    subject.build(
        repository_root=ROOT,
        output_dir=rebuilt,
        external_review_path=_review_path(),
        source_identity=(source.source_commit, source.source_tree),
    )
    assert _files(rebuilt) == actual
    assert _files(ROOT / models.V229_DIR) == before
