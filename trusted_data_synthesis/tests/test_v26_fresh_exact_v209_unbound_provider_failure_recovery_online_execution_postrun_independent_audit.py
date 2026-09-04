# ruff: noqa: E501
from __future__ import annotations

import ast
import hashlib
import inspect
import json
import subprocess
from collections import Counter
from pathlib import Path
from typing import Any

import pytest

from trusted_synthesis.experiments.vtdo_experiment import (
    phase1_v26_fresh_exact_v209_unbound_provider_failure_recovery_online_execution_postrun_independent_audit as subject,
)
from trusted_synthesis.experiments.vtdo_experiment import (
    phase1_v26_fresh_exact_v209_unbound_provider_failure_recovery_online_execution_postrun_independent_audit_models as models,
)

ROOT = Path(__file__).resolve().parents[2]
REVIEW = Path(
    "/home/zhuxinrui/.codex/attachments/515ba512-5135-4e37-a2f3-3b01ea89b1d9/pasted-text.txt"
)


def _formal_dir() -> Path:
    return ROOT / models.OUTPUT_DIR


def _load(root: Path, name: str) -> dict[str, Any]:
    value = json.loads((root / name).read_bytes())
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
    if formal.is_dir() and (formal / "source_authority_audit.json").is_file():
        source = _load(formal, "source_authority_audit.json")
        source_identity = (str(source["source_commit"]), str(source["source_tree"]))
        review = formal / "external_review.txt"
    else:
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
        review = REVIEW
    output = tmp_path_factory.mktemp("v26-234") / "formal"
    subject.build(
        repository_root=ROOT,
        output_dir=output,
        external_review_path=review,
        source_identity=source_identity,
    )
    return output


def test_external_scope_source_and_exact_v233_freeze(built: Path) -> None:
    authorization = models.ExternalAuthorization.model_validate(
        _load(built, "external_authorization.json")
    )
    source = models.SourceAuthorityAudit.model_validate(_load(built, "source_authority_audit.json"))
    freeze = models.V233ExecutionFreezeAudit.model_validate(
        _load(built, "v233_execution_freeze_audit.json")
    )
    assert authorization.audit_decision == "PASS_AS_SCOPED"
    assert hashlib.sha256((built / "external_review.txt").read_bytes()).hexdigest() == (
        models.EXTERNAL_REVIEW_SHA256
    )
    assert source.commit_tree_relations_verified == 2
    assert source.committed_current_member_matches == 4
    assert source.v233_source_commit == models.V233_SOURCE_COMMIT
    assert source.v233_source_tree == models.V233_SOURCE_TREE
    assert freeze.file_count == 381
    assert freeze.manifest_member_count == freeze.manifest_actual_byte_matches == 380
    assert freeze.manifest_file_sha256 == models.V233_MANIFEST_SHA256
    assert freeze.summary_used_as_outcome_oracle is False


def test_33_source_rows_55_local_prefixes_and_33_handoffs(built: Path) -> None:
    audit = models.RecoveryAuthorityAudit.model_validate(
        _load(built, "recovery_authority_audit.json")
    )
    assert len(audit.rows) == audit.exact_source_row_count == audit.exact_recovery_job_count == 33
    assert sum(row.successful_prefix_projection_count for row in audit.rows) == 55
    assert audit.local_prefix_projection_count == 55
    assert audit.historical_prefix_provider_reissue_count == 0
    assert audit.captured_failed_request_handoff_count == 33
    assert audit.exact_first_fresh_request_matches == 33
    assert all(row.first_fresh_request_match for row in audit.rows)
    assert all(row.first_fresh_certificate_match for row in audit.rows)
    assert all(row.first_fresh_receipt_match for row in audit.rows)


def test_all_64_provider_descriptors_reconstruct_from_actual_artifacts(built: Path) -> None:
    audit = models.ProviderJournalAudit.model_validate(_load(built, "provider_journal_audit.json"))
    assert len(audit.rows) == audit.provider_descriptor_count == 64
    assert audit.provider_artifact_count == 192
    assert Counter(row.status for row in audit.rows) == {
        "succeeded": 47,
        "provider_error": 17,
    }
    assert Counter(row.error_type for row in audit.rows if row.error_type) == {
        "ReasoningBudgetExhaustedError": 16,
        "JSONDecodeError": 1,
    }
    assert audit.first_fresh_handoff_count == 33
    assert audit.per_job_call_count_distribution == {1: 14, 2: 10, 3: 6, 4: 3}
    assert (audit.input_tokens, audit.output_tokens) == (464_481, 637_076)
    assert all(row.descriptor_actual_byte_match for row in audit.rows)
    assert all(row.artifact_actual_byte_matches == 3 for row in audit.rows)


def test_16_terminals_and_80_layers_are_independently_reconstructed(built: Path) -> None:
    audit = models.TerminalReconstructionAudit.model_validate(
        _load(built, "terminal_reconstruction_audit.json")
    )
    assert len(audit.rows) == audit.terminal_record_count == 16
    assert tuple(row.job_ordinal for row in audit.rows) == models.TERMINAL_ORDINALS
    assert (audit.completed_qualified_count, audit.completed_invalid_count) == (8, 1)
    assert audit.final_response_abi_invalid_count == 7
    assert audit.independently_derived_terminal_matches == 16
    assert audit.independently_derived_decision_byte_matches == 16
    assert audit.five_layer_file_count == audit.layer_actual_byte_matches == 80
    assert audit.layer_parent_matches == audit.layer_namespace_matches == 80
    assert all(row.layer_actual_byte_matches == 5 for row in audit.rows)
    assert all(row.record_actual_byte_match for row in audit.rows)


def test_17_failures_end_at_the_last_fresh_call_without_terminalization(built: Path) -> None:
    audit = models.FailureReconstructionAudit.model_validate(
        _load(built, "failure_reconstruction_audit.json")
    )
    assert len(audit.rows) == audit.failure_record_count == 17
    assert tuple(row.job_ordinal for row in audit.rows) == models.FAILURE_ORDINALS
    assert audit.unbound_provider_failure_count == 17
    assert audit.host_failure_count == 0
    assert (audit.reasoning_budget_error_count, audit.json_decode_error_count) == (16, 1)
    assert audit.final_call_failure_matches == audit.no_later_call_matches == 17
    assert audit.terminal_evidence_admitted_count == 0
    assert audit.five_layer_evidence_admitted_count == 0
    assert all(row.prior_fresh_calls_succeeded for row in audit.rows)
    assert all(row.final_fresh_call_failed and row.no_later_provider_call for row in audit.rows)


def test_exact_partition_remains_incomplete_and_unestimated(built: Path) -> None:
    partition = models.ExactPartitionAudit.model_validate(
        _load(built, "exact_partition_audit.json")
    )
    decision = models.IndependentAuditDecision.model_validate(
        _load(built, "independent_audit_decision.json")
    )
    transition = models.Transition.model_validate(_load(built, "prospective_transition.json"))
    assert partition.exact_job_count == partition.attempted_job_count == 33
    assert (partition.terminal_record_count, partition.failure_record_count) == (16, 17)
    assert partition.execution_status == "incomplete"
    assert partition.scientific_denominator_complete is False
    assert partition.execution_summary_actual_byte_match
    assert partition.transition_actual_byte_match
    assert partition.execution_summary_used_as_outcome_oracle is False
    assert decision.attempted_recovery_population_closed
    assert decision.terminal_evidence_set_complete is False
    assert decision.provider_failure_terminalized is False
    assert decision.empirical_estimate_materialized is False
    assert transition.next_decision == models.NEXT_DECISION
    assert transition.next_stage_authorized is False
    assert transition.provider_execution_authorized is False
    assert transition.recovery_retry_authorized is False
    assert transition.empirical_estimation_authorized is False


def test_scope_and_gate_are_noncompensatory_and_zero_provider(built: Path) -> None:
    scope = models.ScopeBoundaryAudit.model_validate(_load(built, "scope_boundary_audit.json"))
    gate = models.GateEvaluation.model_validate(_load(built, "gate_evaluation.json"))
    assert scope.provider_calls == scope.credential_lookups == scope.client_constructions == 0
    assert scope.recovery_job_retries == scope.historical_terminal_backfills == 0
    assert scope.historical_v26_226_writes == scope.empirical_estimates == 0
    assert scope.execution_summary_oracle_calls == scope.v233_execution_helper_calls == 0
    assert gate.passed_count == 7
    assert gate.failed_count == 0
    assert gate.noncompensatory
    assert all(row.passed for row in gate.rows)


def test_empty_directory_rebuild_is_byte_identical(built: Path, tmp_path: Path) -> None:
    source = models.SourceAuthorityAudit.model_validate(_load(built, "source_authority_audit.json"))
    second = tmp_path / "rebuild"
    subject.build(
        repository_root=ROOT,
        output_dir=second,
        external_review_path=built / "external_review.txt",
        source_identity=(source.source_commit, source.source_tree),
    )
    assert _files(built) == _files(second)


def test_implementation_does_not_import_or_call_v233_executor() -> None:
    source = inspect.getsource(subject)
    tree = ast.parse(source)
    imported_names = {
        alias.name
        for node in ast.walk(tree)
        if isinstance(node, ast.ImportFrom)
        for alias in node.names
    }
    called_names = {
        node.func.attr if isinstance(node.func, ast.Attribute) else node.func.id
        for node in ast.walk(tree)
        if isinstance(node, ast.Call) and isinstance(node.func, (ast.Attribute, ast.Name))
    }
    assert (
        "phase1_v26_fresh_exact_v209_unbound_provider_failure_recovery_online_execution"
        not in imported_names
    )
    assert not called_names & {
        "prepare_execution",
        "execute",
        "_execute_job",
        "_persist_chain",
        "_derive_recovery_terminal",
        "complete_body",
        "complete_json",
        "urlopen",
    }
