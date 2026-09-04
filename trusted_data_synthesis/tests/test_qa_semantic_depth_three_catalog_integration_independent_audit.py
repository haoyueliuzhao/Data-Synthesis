from __future__ import annotations

import hashlib
import json
import subprocess
from pathlib import Path

import pytest

from trusted_synthesis.experiments import (
    qa_semantic_depth_three_catalog_integration_independent_audit as audit_package,
)
from trusted_synthesis.experiments.qa_semantic_depth_three_catalog_integration_independent_audit.audit import (  # noqa: E501
    AuditError,
    build_qa_semantic_depth_three_catalog_integration_independent_audit,
    write_qa_semantic_depth_three_catalog_integration_independent_audit_artifacts,
)

models = audit_package.models

ROOT = Path(__file__).resolve().parents[2]
REVIEW = Path(
    "/home/zhuxinrui/.codex/attachments/62407e77-ee4c-4930-9802-9071381b8576/pasted-text.txt"
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
def products() -> models.AuditProducts:
    return build_qa_semantic_depth_three_catalog_integration_independent_audit(
        repo_root=ROOT,
        external_audit_path=REVIEW,
        source_commit=_git("rev-parse", "HEAD"),
        source_tree=_git("rev-parse", "HEAD^{tree}"),
    )


def test_exact_review_directive_and_candidate_freeze(products: models.AuditProducts) -> None:
    assert len(products.external_review_bytes) == 14_751
    assert hashlib.sha256(products.external_review_bytes).hexdigest() == (
        models.EXTERNAL_REVIEW_SHA256
    )
    assert products.operator_directive_bytes == models.OPERATOR_DIRECTIVE.encode()
    freeze = products.candidate_freeze
    assert (freeze["file_count"], freeze["total_bytes"]) == (23, 183_833)
    assert (freeze["manifest_member_count"], freeze["manifest_member_bytes"]) == (
        22,
        180_424,
    )
    assert freeze["manifest_file_sha256"] == models.CANDIDATE_MANIFEST_SHA256
    assert freeze["manifest_id"] == models.CANDIDATE_MANIFEST_ID
    assert freeze["artifact_root"] == models.CANDIDATE_ARTIFACT_ROOT
    assert freeze["candidate_integration_rows_used_as_oracle"] is False


def test_detached_rebuild_is_exact_and_credential_free(products: models.AuditProducts) -> None:
    audit = products.detached_rebuild
    assert audit["archived_source_file_count"] == 726
    assert audit["saved_file_count"] == audit["rebuilt_file_count"] == 23
    assert audit["saved_bytes"] == audit["rebuilt_bytes"] == 183_833
    assert audit["path_matches"] == audit["sha256_matches"] == 23
    assert audit["actual_byte_matches"] == 23
    assert audit["manifest_members_revalidated"] == 22
    assert audit["credential_like_environment_keys"] == 0
    assert audit["credential_lookups"] == audit["provider_calls"] == audit["gpu_jobs"] == 0


def test_source_and_historical_catalog_are_independently_reconstructed(
    products: models.AuditProducts,
) -> None:
    source = products.candidate_source_authority
    assert source["requested_commit"] == models.CANDIDATE_SOURCE_COMMIT
    assert source["requested_tree"] == models.CANDIDATE_SOURCE_TREE
    assert source["member_count"] == 4
    assert source["git_blob_matches"] == source["committed_current_byte_matches"] == 4
    assert source["candidate_binding_actual_byte_match"] is True
    historical = products.historical_catalog_audit
    assert historical["task_types"] == models.HISTORICAL_TASK_TYPES
    assert historical["task_count"] == historical["pattern_count"] == 8
    assert historical["snapshot_actual_byte_match"] is True
    assert historical["historical_objects_modified"] is False


def test_catalog_registration_and_resolution_are_independently_rebuilt(
    products: models.AuditProducts,
) -> None:
    audit = products.catalog_authority_audit
    assert audit["candidate_catalog_id"] == models.CANDIDATE_CATALOG_ID
    assert audit["historical_task_count"] == 8
    assert audit["extension_task_types"] == models.EXTENSION_TASK_TYPES
    assert audit["extension_operation_ids"] == models.EXTENSION_OPERATION_IDS
    assert audit["extension_task_counts"] == {task: 1 for task in models.EXTENSION_TASK_TYPES}
    assert audit["extension_operation_counts"] == {
        operation: 1 for operation in models.EXTENSION_OPERATION_IDS
    }
    assert set(audit["extension_operation_roles"].values()) == {"semantic"}
    assert audit["catalog_actual_byte_match"] is True
    assert audit["resolution_receipt_actual_byte_matches"] == 2
    assert audit["candidate_catalog_helpers_called"] == 0


def test_two_fixed_inputs_rebuild_and_execute_all_fourteen_nodes(
    products: models.AuditProducts,
) -> None:
    assert tuple(row["case_id"] for row in products.case_rows) == models.CASE_IDS
    assert tuple(row["task_type"] for row in products.case_rows) == models.EXTENSION_TASK_TYPES
    assert all(row["receipt_actual_byte_match"] for row in products.case_rows)
    assert all(row["package_actual_byte_match"] for row in products.case_rows)
    assert all(row["execution_actual_byte_match"] for row in products.case_rows)
    assert all(row["verification_actual_byte_match"] for row in products.case_rows)
    assert all(row["assessment_actual_byte_match"] for row in products.case_rows)
    assert all(row["depth_metrics_actual_byte_match"] for row in products.case_rows)
    assert all(row["candidate_integration_row_actual_byte_match"] for row in products.case_rows)
    assert all(row["semantic_operation_depth"] == 3 for row in products.case_rows)
    assert all(row["answer_schema_correct"] for row in products.case_rows)
    assert all(row["answer_correct"] and row["citation_correct"] for row in products.case_rows)
    assert all(row["quality_accepted"] for row in products.case_rows)
    execution = products.execution_audit
    assert execution["executed_node_count"] == execution["oracle_verified_node_count"] == 14
    assert execution["semantic_operation_depth_distribution"] == {"3": 2}
    assert execution["candidate_input_helper_calls"] == 0
    assert execution["candidate_compile_helper_calls"] == 0
    assert execution["candidate_integration_rows_used_as_oracle"] is False


def test_eight_direct_attacks_reject_at_independent_typed_boundaries(
    products: models.AuditProducts,
) -> None:
    audit = products.negative_audit
    assert (audit["attempted_count"], audit["rejected_count"], audit["accepted_count"]) == (
        8,
        8,
        0,
    )
    assert tuple(row["name"] for row in audit["controls"]) == models.ATTACK_NAMES
    assert tuple(row["rejection_stage"] for row in audit["controls"]) == models.ATTACK_STAGES
    assert all(row["exception_type"] == "AuditError" for row in audit["controls"])
    assert audit["candidate_name_stage_reason_matches"] == 8
    assert audit["candidate_attack_helper_calls"] == 0
    assert audit["output_writes"] == audit["provider_calls"] == 0


def test_scope_gate_decision_and_transition_are_narrow(products: models.AuditProducts) -> None:
    scope = products.scope_audit
    assert scope["audit_source_commit"] == _git("rev-parse", "HEAD")
    assert scope["audit_source_tree"] == _git("rev-parse", "HEAD^{tree}")
    assert tuple(row["relative_path"] for row in scope["audit_source_members"]) == (
        models.AUDIT_SOURCE_PATHS
    )
    assert scope["audit_source_member_count"] == 3
    assert scope["audit_source_current_byte_matches"] == 3
    assert scope["helper_boundary_passed"] is True
    assert not any(
        scope[key]
        for key in (
            "provider_calls",
            "credential_lookups",
            "gpu_jobs",
            "archive_selections",
            "benchmark_rows",
            "empirical_estimates",
            "catalog_promotions",
            "qa_release_objects",
            "mainline_recovery_authorizations_read",
            "mainline_recovery_authorizations_consumed",
        )
    )
    assert products.gate["passed"] == 8 and products.gate["failed"] == 0
    assert tuple(products.gate["gates"]) == models.GATE_NAMES
    assert all(products.gate["gates"].values())
    assert products.decision["decision"] == models.DECISION
    assert products.decision["overall_qa_sufficiency_established"] is False
    assert products.transition["next_stage_authorized"] is False
    assert products.transition["prospective_next_stage"] == models.PROSPECTIVE_NEXT_STAGE


def test_writer_is_exact_reproducible_and_self_excluding(
    products: models.AuditProducts, tmp_path: Path
) -> None:
    left = tmp_path / "left"
    right = tmp_path / "right"
    write_qa_semantic_depth_three_catalog_integration_independent_audit_artifacts(products, left)
    write_qa_semantic_depth_three_catalog_integration_independent_audit_artifacts(products, right)
    assert _files(left) == _files(right)
    files = _files(left)
    manifest = json.loads(files["artifact_manifest.json"])
    assert manifest["self_excluding"] is True
    assert manifest["file_count"] == len(manifest["members"]) == len(files) - 1
    for row in manifest["members"]:
        payload = files[row["relative_path"]]
        assert row["byte_count"] == len(payload)
        assert row["sha256"] == hashlib.sha256(payload).hexdigest()
    assert files["external_review.txt"] == REVIEW.read_bytes()
    assert files["operator_directive.txt"] == models.OPERATOR_DIRECTIVE.encode()


def test_changed_review_rejects(tmp_path: Path) -> None:
    changed = tmp_path / "changed.txt"
    changed.write_bytes(REVIEW.read_bytes() + b"\n")
    with pytest.raises(AuditError, match="review"):
        build_qa_semantic_depth_three_catalog_integration_independent_audit(
            repo_root=ROOT,
            external_audit_path=changed,
            source_commit=_git("rev-parse", "HEAD"),
            source_tree=_git("rev-parse", "HEAD^{tree}"),
        )
