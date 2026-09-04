from __future__ import annotations

import hashlib
import json
import subprocess
from pathlib import Path

import pytest

from trusted_synthesis.experiments.qa_semantic_depth_three_plus_independent_audit import models
from trusted_synthesis.experiments.qa_semantic_depth_three_plus_independent_audit.audit import (
    AuditError,
    build_qa_semantic_depth_three_plus_independent_audit,
    write_qa_semantic_depth_three_plus_independent_audit_artifacts,
)

ROOT = Path(__file__).resolve().parents[2]
REVIEW = Path(
    "/home/zhuxinrui/.codex/attachments/71b6ed85-edaf-4e59-8415-c271f60989fe/pasted-text.txt"
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
    return build_qa_semantic_depth_three_plus_independent_audit(
        repo_root=ROOT,
        external_audit_path=REVIEW,
        source_commit="1" * 40,
        source_tree="1" * 40,
    )


def test_exact_review_directive_and_candidate_freeze(products: models.AuditProducts) -> None:
    assert len(products.external_review_bytes) == 14_928
    assert hashlib.sha256(products.external_review_bytes).hexdigest() == (
        models.EXTERNAL_REVIEW_SHA256
    )
    assert products.operator_directive_bytes == "参照审计执行QA链路后续实验".encode()
    freeze = products.candidate_freeze
    assert (freeze["file_count"], freeze["total_bytes"]) == (21, 162_669)
    assert (freeze["manifest_member_count"], freeze["manifest_member_bytes"]) == (
        20,
        159_547,
    )
    assert freeze["manifest_id"] == models.CANDIDATE_MANIFEST_ID
    assert freeze["artifact_root"] == models.CANDIDATE_ARTIFACT_ROOT
    assert freeze["candidate_coverage_audit_used_as_oracle"] is False


def test_detached_rebuild_is_exact_and_credential_free(products: models.AuditProducts) -> None:
    audit = products.detached_rebuild
    assert audit["archived_source_file_count"] == 715
    assert audit["saved_file_count"] == audit["rebuilt_file_count"] == 21
    assert audit["saved_bytes"] == audit["rebuilt_bytes"] == 162_669
    assert audit["path_matches"] == audit["sha256_matches"] == 21
    assert audit["actual_byte_matches"] == 21
    assert audit["manifest_members_revalidated"] == 20
    assert audit["credential_like_environment_keys"] == 0
    assert audit["credential_lookups"] == audit["provider_calls"] == audit["gpu_jobs"] == 0


def test_source_and_registry_authority_are_independently_rebuilt(
    products: models.AuditProducts,
) -> None:
    source = products.source_authority
    assert source["requested_commit"] == models.CANDIDATE_SOURCE_COMMIT
    assert source["requested_tree"] == models.CANDIDATE_SOURCE_TREE
    assert source["member_count"] == 5
    assert source["git_blob_matches"] == source["committed_current_byte_matches"] == 5
    assert source["candidate_binding_actual_byte_match"] is True
    assert source["candidate_source_helper_calls"] == 0
    registry = products.registry_authority
    assert registry["registry_manifest_sha256"] == models.REGISTRY_MANIFEST_SHA256
    assert registry["extension_roles"] == ("semantic", "semantic", "semantic")
    assert registry["executor_classes"] != registry["oracle_classes"]
    assert registry["candidate_binding_actual_byte_match"] is True
    assert registry["candidate_registry_factory_calls"] == 0


def test_two_source_programs_and_all_fourteen_nodes_reexecute(
    products: models.AuditProducts,
) -> None:
    assert tuple(row["case_id"] for row in products.case_rows) == models.CASE_IDS
    assert tuple(row["task_type"] for row in products.case_rows) == models.TASK_TYPES
    assert all(
        row["source_program_reconstructed_from_pattern_and_evidence"] for row in products.case_rows
    )
    assert all(row["package_actual_byte_match"] for row in products.case_rows)
    assert all(row["execution_actual_byte_match"] for row in products.case_rows)
    assert all(row["independent_node_replay_passed"] for row in products.case_rows)
    assert all(row["answer_schema_correct"] for row in products.case_rows)
    assert all(row["answer_correct"] and row["citation_correct"] for row in products.case_rows)
    assert all(row["quality_accepted"] for row in products.case_rows)
    execution = products.execution_audit
    assert execution["exact_case_count"] == 2
    assert execution["executed_node_count"] == execution["oracle_verified_node_count"] == 14
    assert execution["candidate_coverage_audit_used_as_selector"] is False
    assert execution["candidate_preflight_helper_calls"] == 0


def test_depth_and_topology_are_derived_from_dag_and_registry(
    products: models.AuditProducts,
) -> None:
    audit = products.depth_topology_audit
    assert audit["semantic_operation_depth_distribution"] == {"3": 2}
    assert audit["structural_dependency_depth_distribution"] == {"4": 2}
    assert audit["workflow_interaction_depth_distribution"] == {"5": 2}
    assert audit["topology_distribution"] == {
        "branch_and_merge": 1,
        "serial_chain": 1,
    }
    assert audit["topology_derived_from_dag"] is True
    assert audit["registry_roles_derived_independently"] is True
    assert audit["candidate_topology_labels_used_as_oracle"] is False
    by_case = {row["case_id"]: row for row in products.case_rows}
    assert by_case["serial_margin_target_gap"]["critical_semantic_paths"] == (
        ("ratio", "scale_ratio_percent", "signed_percentage_point_gap"),
    )
    assert by_case["branch_merge_growth_gap"]["critical_semantic_paths"] == (
        ("growth", "signed_percentage_point_gap", "absolute_percentage_point_gap"),
    )


def test_seven_direct_attacks_reject_at_observed_typed_boundaries(
    products: models.AuditProducts,
) -> None:
    audit = products.negative_audit
    assert (audit["attempted_count"], audit["rejected_count"], audit["accepted_count"]) == (
        7,
        7,
        0,
    )
    assert tuple(row["name"] for row in audit["controls"]) == models.ATTACK_NAMES
    assert tuple(row["rejection_stage"] for row in audit["controls"]) == models.ATTACK_STAGES
    assert all(row["exception_type"] == "AuditError" for row in audit["controls"])
    assert audit["rejection_stages_derived_from_typed_exceptions"] is True
    assert audit["output_writes"] == audit["provider_calls"] == 0


def test_scope_gate_decision_and_transition_remain_offline(
    products: models.AuditProducts,
) -> None:
    scope = products.scope_audit
    assert scope["audit_source_commit"] == _git("rev-parse", "HEAD")
    assert scope["audit_source_tree"] == _git("rev-parse", "HEAD^{tree}")
    assert tuple(row["relative_path"] for row in scope["audit_source_members"]) == (
        models.AUDIT_SOURCE_PATHS
    )
    assert scope["audit_source_member_count"] == 3
    assert scope["audit_source_current_byte_matches"] == 3
    assert scope["helper_boundary_passed"] is True
    assert scope["candidate_helper_calls"] == scope["candidate_oracle_calls"] == 0
    assert not any(
        scope[key]
        for key in (
            "provider_calls",
            "credential_lookups",
            "gpu_jobs",
            "archive_selections",
            "benchmark_rows",
            "empirical_estimates",
            "online_job_manifests",
            "catalog_promotions",
            "qa_release_objects",
            "vtdo_rows",
            "training_rows",
            "production_rows",
        )
    )
    assert products.gate["passed"] == 8 and products.gate["failed"] == 0
    assert tuple(products.gate["gates"]) == models.GATE_NAMES
    assert all(products.gate["gates"].values())
    assert products.decision["decision"] == models.DECISION
    assert products.transition["next_stage_authorized"] is False
    assert products.transition["prospective_next_stage"] == models.PROSPECTIVE_NEXT_STAGE


def test_writer_is_exact_reproducible_and_self_excluding(
    products: models.AuditProducts, tmp_path: Path
) -> None:
    left = tmp_path / "left"
    right = tmp_path / "right"
    write_qa_semantic_depth_three_plus_independent_audit_artifacts(products, left)
    write_qa_semantic_depth_three_plus_independent_audit_artifacts(products, right)
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
        build_qa_semantic_depth_three_plus_independent_audit(
            repo_root=ROOT,
            external_audit_path=changed,
            source_commit="1" * 40,
            source_tree="1" * 40,
        )
