from __future__ import annotations

import hashlib
import json
import subprocess
from pathlib import Path

import pytest

from trusted_synthesis.experiments.qa_generator_source_authority_independent_audit import models
from trusted_synthesis.experiments.qa_generator_source_authority_independent_audit.audit import (
    IndependentAuditError,
    build_qa_generator_source_authority_independent_audit,
    write_qa_generator_source_authority_independent_audit_artifacts,
)

ROOT = Path(__file__).resolve().parents[2]
REVIEW = Path(
    "/home/zhuxinrui/.codex/attachments/cb81f5c9-2bd3-4c27-a76e-4d9df9b5862d/pasted-text.txt"
)


def _git(*arguments: str) -> str:
    return subprocess.run(
        ("git", "-C", str(ROOT), *arguments),
        check=True,
        capture_output=True,
        text=True,
    ).stdout.strip()


def _files(root: Path) -> dict[str, bytes]:
    return {
        path.relative_to(root).as_posix(): path.read_bytes()
        for path in root.rglob("*")
        if path.is_file()
    }


@pytest.fixture(scope="module")
def products() -> models.QAGeneratorSourceAuthorityIndependentAuditProducts:
    return build_qa_generator_source_authority_independent_audit(
        repo_root=ROOT,
        external_audit_path=REVIEW,
        source_commit="1" * 40,
        source_tree="1" * 40,
    )


def test_exact_external_scope_and_candidate_freeze(
    products: models.QAGeneratorSourceAuthorityIndependentAuditProducts,
) -> None:
    assert products.external_review_bytes == REVIEW.read_bytes()
    assert len(products.external_review_bytes) == 12_251
    assert (
        hashlib.sha256(products.external_review_bytes).hexdigest() == models.EXTERNAL_REVIEW_SHA256
    )
    assert products.operator_directive_bytes.decode() == "参照审计报告开展实验"
    freeze = products.candidate_freeze
    assert (freeze.file_count, freeze.total_bytes) == (24, 463_886)
    assert (freeze.manifest_member_count, freeze.manifest_member_bytes) == (23, 460_263)
    assert freeze.path_matches == freeze.sha256_matches == 24
    assert freeze.byte_count_matches == freeze.actual_byte_matches == 24
    assert freeze.manifest_members_revalidated == 23
    assert freeze.candidate_report_used_as_oracle is False
    assert freeze.candidate_gate_used_as_oracle is False


def test_detached_rebuild_is_exact_and_credential_free(
    products: models.QAGeneratorSourceAuthorityIndependentAuditProducts,
) -> None:
    audit = products.detached_rebuild
    assert audit.archived_source_file_count == 703
    assert audit.saved_file_count == audit.rebuilt_file_count == 24
    assert audit.path_matches == audit.sha256_matches == 24
    assert audit.actual_byte_matches == 24
    assert audit.manifest_members_revalidated == 23
    assert audit.credential_like_environment_keys == 0
    assert audit.credential_lookups == audit.provider_calls == audit.gpu_jobs == 0


def test_git_authority_is_independently_rederived_for_all_members(
    products: models.QAGeneratorSourceAuthorityIndependentAuditProducts,
) -> None:
    audit = products.git_source_authority_audit
    assert audit.source_group_count == 2
    assert audit.total_member_count == 19
    assert audit.commit_object_matches == audit.commit_tree_relation_matches == 2
    assert audit.committed_member_byte_matches == audit.current_member_byte_matches == 19
    assert all(
        row.git_blob_matches
        for group in (audit.generator_group, audit.repair_group)
        for row in group.members
    )
    assert audit.candidate_binding_actual_byte_matches == 2
    assert audit.generator_group.candidate_binding_used_as_authority is False
    assert audit.repair_group.candidate_binding_used_as_authority is False
    assert audit.candidate_source_binding_helper_calls == 0


def test_legacy_counterexample_and_five_source_attacks_reject(
    products: models.QAGeneratorSourceAuthorityIndependentAuditProducts,
) -> None:
    legacy = products.legacy_counterexample_audit
    assert legacy.legacy_binding_constructed is True
    assert legacy.legacy_g2_passed is True
    assert legacy.new_authority_rejected is True
    assert legacy.rejection_stage == "git_commit_resolution"
    attack = products.source_attack_audit
    assert (attack.attempted_count, attack.rejected_count, attack.accepted_count) == (5, 5, 0)
    assert tuple(item.name for item in attack.controls) == models.SOURCE_ATTACK_NAMES
    assert tuple(item.rejection_stage for item in attack.controls) == (
        "git_commit_resolution",
        "commit_tree_relation",
        "committed_member_bytes",
        "committed_member_bytes",
        "current_worktree_member_bytes",
    )
    assert attack.output_write_count == attack.provider_calls == 0


def test_eight_fixed_fixtures_are_independently_reverified(
    products: models.QAGeneratorSourceAuthorityIndependentAuditProducts,
) -> None:
    audit = products.fixture_audit
    assert tuple(row.task_type for row in audit.rows) == models.REGISTERED_TASK_TYPES
    assert audit.registered_task_count == 8
    assert audit.generator_success_count == audit.exact_program_execution_count == 8
    assert audit.independent_node_replay_count == audit.operation_correct_count == 8
    assert all(row.candidate_object_matches == 6 for row in audit.rows)
    assert audit.answer_schema_correct_count == audit.answer_correct_count == 8
    assert audit.citation_correct_count == audit.evaluator_accepted_count == 8
    assert audit.insufficient_capability_count == 0


def test_four_depth_metrics_are_independent_exact_and_shallow(
    products: models.QAGeneratorSourceAuthorityIndependentAuditProducts,
) -> None:
    audit = products.depth_metric_audit
    assert audit.candidate_depth_helper_calls == 0
    assert audit.registry_manifest_sha256 == models.REGISTRY_MANIFEST_SHA256
    assert audit.node_count_distribution == {"1": 3, "3": 3, "4": 1, "7": 1}
    assert audit.structural_dependency_depth_distribution == {"1": 3, "2": 4, "3": 1}
    assert audit.semantic_operation_depth_distribution == {"0": 1, "1": 6, "2": 1}
    assert audit.workflow_interaction_depth_distribution == {"2": 1, "3": 6, "4": 1}
    assert audit.maximum_structural_dependency_depth == 3
    assert audit.maximum_semantic_operation_depth == 2
    assert audit.semantic_depth_three_plus_count == 0
    assert audit.output_dependency_closed_count == audit.exact_source_program_admitted_count == 8
    assert all(row.candidate_metric_row_match for row in audit.rows)


def test_three_depth_attacks_reject_with_final_answer_retained(
    products: models.QAGeneratorSourceAuthorityIndependentAuditProducts,
) -> None:
    audit = products.depth_attack_audit
    assert (audit.attempted_count, audit.rejected_count, audit.accepted_count) == (3, 3, 0)
    assert tuple(item.name for item in audit.controls) == models.DEPTH_ATTACK_NAMES
    assert tuple(item.rejection_stage for item in audit.controls) == (
        "exact_source_program_admission",
        "exact_source_program_admission",
        "output_dependency_closure",
    )
    assert all(item.final_answer_retained for item in audit.controls)
    assert audit.output_write_count == audit.provider_calls == audit.gpu_jobs == 0


def test_scope_gate_decision_and_transition_remain_non_online(
    products: models.QAGeneratorSourceAuthorityIndependentAuditProducts,
) -> None:
    scope = products.scope_audit
    audit_source = (ROOT / scope.audit_source_relative_path).read_bytes()
    assert scope.audit_source_commit == _git("rev-parse", "HEAD")
    assert scope.audit_source_tree == _git("rev-parse", "HEAD^{tree}")
    assert scope.audit_source_sha256 == hashlib.sha256(audit_source).hexdigest()
    assert scope.audit_source_byte_count == len(audit_source)
    assert scope.audit_source_commit_tree_relation_verified is True
    assert scope.audit_source_current_bytes_match is True
    assert scope.helper_boundary_passed is True
    assert scope.candidate_helper_calls == scope.candidate_oracle_calls == 0
    assert not any(
        (
            scope.provider_calls,
            scope.credential_lookups,
            scope.gpu_jobs,
            scope.online_job_manifests,
            scope.empirical_rows,
            scope.qa_release_objects,
            scope.vtdo_rows,
            scope.training_rows,
            scope.production_rows,
        )
    )
    gate = products.gate_evaluation
    assert gate.passed == 8 and gate.failed == 0
    assert tuple(gate.gates) == models.GATE_NAMES
    assert all(gate.gates.values())
    assert products.decision.decision == models.DECISION
    assert products.transition.next_stage == models.NEXT_STAGE
    assert products.transition.next_stage_authorized is False
    assert products.transition.provider_execution_authorized is False
    assert products.transition.gpu_execution_authorized is False
    assert products.transition.qa_release_authorized is False


def test_writer_is_exact_reproducible_and_self_excluding(
    products: models.QAGeneratorSourceAuthorityIndependentAuditProducts,
    tmp_path: Path,
) -> None:
    left = tmp_path / "left"
    right = tmp_path / "right"
    write_qa_generator_source_authority_independent_audit_artifacts(products, left)
    write_qa_generator_source_authority_independent_audit_artifacts(products, right)
    assert _files(left) == _files(right)
    files = _files(left)
    manifest = json.loads(files["artifact_manifest.json"])
    assert manifest["self_excluding"] is True
    assert manifest["file_count"] == len(manifest["members"]) == len(files) - 1
    assert "artifact_manifest.json" not in {row["relative_path"] for row in manifest["members"]}
    for row in manifest["members"]:
        payload = files[row["relative_path"]]
        assert row["byte_count"] == len(payload)
        assert row["sha256"] == hashlib.sha256(payload).hexdigest()
    assert files["external_review.txt"] == REVIEW.read_bytes()
    assert files["operator_directive.txt"] == "参照审计报告开展实验".encode()


def test_wrong_review_and_existing_output_reject(
    tmp_path: Path,
) -> None:
    changed = tmp_path / "changed.txt"
    changed.write_bytes(REVIEW.read_bytes() + b"\n")
    with pytest.raises(IndependentAuditError, match="review"):
        build_qa_generator_source_authority_independent_audit(
            repo_root=ROOT,
            external_audit_path=changed,
            source_commit=_git("rev-parse", "HEAD"),
            source_tree=_git("rev-parse", "HEAD^{tree}"),
        )
