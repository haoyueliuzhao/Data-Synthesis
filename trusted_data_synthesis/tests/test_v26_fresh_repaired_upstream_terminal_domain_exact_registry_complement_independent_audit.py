# ruff: noqa: E501, SLF001
from __future__ import annotations

import ast
import hashlib
import json
import os
from pathlib import Path
from typing import Any

import pytest

from trusted_synthesis.experiments.vtdo_experiment import (
    phase1_v26_fresh_repaired_upstream_terminal_domain_exact_registry_complement_independent_audit as subject,
)
from trusted_synthesis.experiments.vtdo_experiment import (
    phase1_v26_fresh_repaired_upstream_terminal_domain_exact_registry_complement_independent_audit_models as models,
)

ROOT = Path(__file__).resolve().parents[2]
ATTACHED_REVIEW = Path(
    "/home/zhuxinrui/.codex/attachments/ed3b375c-9b15-415b-acec-a7742a117bfb/pasted-text.txt"
)


def _review_path() -> Path:
    explicit = os.environ.get("V219_EXTERNAL_REVIEW")
    formal = ROOT / "trusted_data_synthesis" / subject.OUTPUT_DIR / "external_review.txt"
    path = Path(explicit) if explicit else (formal if formal.is_file() else ATTACHED_REVIEW)
    if not path.is_file():
        pytest.skip("exact v26.219 external review is unavailable")
    return path


def _load(root: Path, name: str) -> dict[str, Any]:
    return json.loads((root / name).read_bytes())


def _files(root: Path) -> dict[str, bytes]:
    return {
        path.relative_to(root).as_posix(): path.read_bytes()
        for path in root.rglob("*")
        if path.is_file()
    }


@pytest.fixture(scope="module")
def built(tmp_path_factory: pytest.TempPathFactory) -> Path:
    formal = ROOT / "trusted_data_synthesis" / subject.OUTPUT_DIR
    if formal.is_dir():
        source = _load(formal, "source_identity.json")
        source_identity = (str(source["source_commit"]), str(source["source_tree"]))
    else:
        source_identity = ("1" * 40, "2" * 40)
    output = tmp_path_factory.mktemp("v26-219") / "formal"
    subject.build(
        repository_root=ROOT,
        output_dir=output,
        external_review_path=_review_path(),
        source_identity=source_identity,
    )
    return output


def test_exact_external_authorization_and_v218_freeze(built: Path) -> None:
    authorization = models.ExternalIndependentAuditAuthorization.model_validate(
        _load(built, "external_independent_audit_authorization.json")
    )
    freeze = models.V218Freeze.model_validate(_load(built, "v218_freeze.json"))
    assert authorization.review_sha256 == subject.EXTERNAL_REVIEW_SHA256
    assert authorization.review_byte_count == 9_045
    assert authorization.operator_directive == subject.OPERATOR_DIRECTIVE
    assert authorization.operator_directive_byte_count == 30
    assert (
        authorization.operator_directive_sha256
        == hashlib.sha256(subject.OPERATOR_DIRECTIVE.encode("utf-8")).hexdigest()
    )
    assert authorization.audit_result == "PASSED_AS_SCOPED"
    assert authorization.blocking_defect == "NONE_FOUND"
    assert authorization.mandatory_revision == "NONE"
    assert authorization.only_authorized_stage == models.CONSUMED_STAGE
    assert not authorization.online_execution_authorized
    assert (freeze.v218_formal_file_count, freeze.v218_formal_total_byte_count) == (
        51,
        1_054_511,
    )
    assert (freeze.v218_manifest_member_count, freeze.v218_manifest_member_byte_count) == (
        50,
        1_044_590,
    )
    assert freeze.v218_source_commit == models.V218_COMMIT
    assert freeze.v218_source_tree == models.V218_TREE
    assert freeze.v218_decision == models.V218_DECISION


def test_independent_source_does_not_call_candidate_helpers() -> None:
    tree = ast.parse((ROOT / subject.AUDIT_FILE).read_text(encoding="utf-8"))
    called = {
        node.func.attr if isinstance(node.func, ast.Attribute) else node.func.id
        for node in ast.walk(tree)
        if isinstance(node, ast.Call) and isinstance(node.func, (ast.Attribute, ast.Name))
    }
    assert not called & {
        "_complement_binding",
        "ExactRegistryComplementAuthority",
        "run_same_length_full_rehash_attack",
        "ArtifactBackedFailureConsumer",
    }


def test_detached_v218_directory_rebuild_is_exact(built: Path) -> None:
    audit = models.DetachedRebuildAudit.model_validate(_load(built, "detached_rebuild_audit.json"))
    assert audit.archived_source_file_count > 0
    assert (
        audit.path_match_count,
        audit.sha256_match_count,
        audit.byte_count_match_count,
        audit.actual_byte_equality_count,
    ) == (51, 51, 51, 51)
    assert audit.rebuilt_total_byte_count == audit.saved_total_byte_count == 1_054_511
    assert audit.manifest_member_revalidation_count == 50
    assert not audit.candidate_report_used_as_outcome_oracle
    assert not audit.candidate_gate_used_as_outcome_oracle
    assert not audit.candidate_complement_audit_used_as_outcome_oracle


def test_registry_complement_is_independently_derived(built: Path) -> None:
    audit = models.IndependentRegistryComplementAudit.model_validate(
        _load(built, "independent_registry_complement_audit.json")
    )
    reachable = {item[0] for item in audit.reachable_terminal_policy_items}
    admitted = set(audit.admitted_terminal_kinds)
    forbidden = set(audit.forbidden_terminal_kinds)
    assert audit.exact_v195_registry_id == models.REGISTRY_ID
    assert (audit.reachable_count, audit.admitted_count, audit.forbidden_count) == (16, 1, 15)
    assert admitted == {"instrument_failure"}
    assert admitted | forbidden == reachable
    assert not admitted & forbidden
    assert "provider_failure_no_payload" in forbidden
    assert "resource_budget_exhausted" in forbidden
    assert "provider_no_payload_failure" not in forbidden
    assert "resource_failure" not in forbidden
    assert audit.correct_registry_names_present == 2
    assert audit.old_misspellings_present == 0
    assert audit.candidate_binding_actual_byte_match
    assert audit.candidate_helper_calls == 0


def test_35_retained_runtime_files_are_independently_byte_exact(built: Path) -> None:
    audit = models.IndependentRetainedRuntimeAudit.model_validate(
        _load(built, "independent_retained_runtime_audit.json")
    )
    assert audit.retained_runtime_file_count == 35
    assert (
        audit.v218_to_v217_path_match_count,
        audit.v218_to_v217_sha256_match_count,
        audit.v218_to_v217_actual_byte_match_count,
        audit.detached_to_v218_actual_byte_match_count,
    ) == (35, 35, 35, 35)
    assert (audit.ingress_receipt_count, audit.five_layer_file_count) == (2, 25)
    assert audit.upstream_artifact_file_count == 8
    assert audit.v217_execution_object_actual_byte_match
    assert not audit.candidate_retained_audit_used_as_outcome_oracle


def test_five_source_exit_persistence_chains_are_independently_reconstructed(
    built: Path,
) -> None:
    audit = models.IndependentSourceExitPersistenceAudit.model_validate(
        _load(built, "independent_source_exit_persistence_audit.json")
    )
    assert tuple(row.exit_code for row in audit.rows) == subject.EXIT_ORDER
    assert tuple(row.terminal_kind for row in audit.rows) == (
        "instrument_failure",
        "instrument_failure",
        "instrument_failure",
        "privacy_rejection",
        "instrument_failure",
    )
    assert audit.source_exit_count == audit.distinct_source_exit_count == 5
    assert (audit.instrument_terminal_count, audit.privacy_terminal_count) == (4, 1)
    assert audit.five_layer_file_count == 25
    assert audit.v217_layer_actual_byte_match_count == 25
    assert audit.detached_layer_actual_byte_match_count == 25
    assert audit.content_identity_match_count == 25
    assert audit.e2_upstream_chain_count == 1
    assert sum(row.e2_upstream_artifact_chain_present for row in audit.rows) == 1
    assert audit.exception_escape_count == audit.empirical_row_count == audit.provider_calls == 0
    assert audit.candidate_execution_helper_calls == 0


def test_independent_full_rehash_attack_scope_gate_and_transition(built: Path) -> None:
    attack = models.IndependentFullRehashAttackAudit.model_validate(
        _load(built, "independent_full_rehash_attack_audit.json")
    )
    scope = models.ScopeBoundaryAudit.model_validate(_load(built, "scope_boundary_audit.json"))
    gate = models.GateEvaluation.model_validate(_load(built, "gate_evaluation.json"))
    decision = models.Decision.model_validate(_load(built, "decision.json"))
    transition = models.Transition.model_validate(_load(built, "prospective_transition.json"))
    assert attack.candidate_forbidden_count == 15
    assert attack.independently_rehashed_object_count == 4
    assert attack.saved_candidate_identity_match_count == 4
    assert attack.rejected
    assert attack.rejection_stage == "independent_registry_complement_admission"
    assert attack.attack_output_writes == attack.candidate_attack_helper_calls == 0
    assert (gate.passed_count, gate.failed_count) == (7, 0)
    assert decision.decision == models.DECISION
    assert transition.next_stage == models.NEXT_STAGE
    assert transition.next_stage_authorized is False
    assert transition.separate_external_decision_required is True
    assert transition.online_authorization_created is False
    assert scope.current_v211_authorization_consumed is False
    assert scope.new_online_authorizations == 0
    assert scope.provider_calls == scope.provider_client_constructions == 0
    assert scope.credential_lookups == scope.empirical_rows == scope.empirical_estimates == 0


def test_complete_directory_rebuild_is_byte_exact(built: Path, tmp_path: Path) -> None:
    source = _load(built, "source_identity.json")
    rebuilt = tmp_path / "rebuilt"
    subject.build(
        repository_root=ROOT,
        output_dir=rebuilt,
        external_review_path=_review_path(),
        source_identity=(str(source["source_commit"]), str(source["source_tree"])),
    )
    assert _files(rebuilt) == _files(built)
