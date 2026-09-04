from __future__ import annotations

import hashlib
import json
import subprocess
from pathlib import Path

import pytest

from trusted_synthesis.core.evaluation.schema import ReleaseDecision
from trusted_synthesis.domains.finance.tasks import FinanceTaskPlugin
from trusted_synthesis.experiments.qa_semantic_depth_three_plus import models
from trusted_synthesis.experiments.qa_semantic_depth_three_plus.preflight import (
    build_qa_semantic_depth_three_plus_preflight,
    write_qa_semantic_depth_three_plus_artifacts,
)

ROOT = Path(__file__).resolve().parents[2]
AUDIT = Path(
    "/home/zhuxinrui/.codex/attachments/74560f22-b488-41ad-9557-52aad4daa1fa/pasted-text.txt"
)


def _git(*arguments: str) -> str:
    return subprocess.run(
        ("git", "-C", str(ROOT), *arguments),
        check=True,
        capture_output=True,
        text=True,
    ).stdout.strip()


@pytest.fixture(scope="module")
def products() -> models.Products:
    return build_qa_semantic_depth_three_plus_preflight(
        repo_root=ROOT,
        external_audit_path=AUDIT,
        source_commit=_git("rev-parse", "HEAD"),
        source_tree=_git("rev-parse", "HEAD^{tree}"),
    )


def _files(root: Path) -> dict[str, bytes]:
    return {
        path.relative_to(root).as_posix(): path.read_bytes()
        for path in root.rglob("*")
        if path.is_file()
    }


def test_exact_external_scope_and_operator_directive(products: models.Products) -> None:
    review = AUDIT.read_bytes()
    directive = models.OPERATOR_DIRECTIVE.encode("utf-8")
    assert len(review) == models.EXTERNAL_AUDIT_BYTE_COUNT == 16_720
    assert hashlib.sha256(review).hexdigest() == models.EXTERNAL_AUDIT_SHA256
    assert products.external_review_bytes == review
    assert len(directive) == models.OPERATOR_DIRECTIVE_BYTE_COUNT == 41
    assert hashlib.sha256(directive).hexdigest() == models.OPERATOR_DIRECTIVE_SHA256
    assert products.operator_directive_bytes == directive
    authorization = products.authorization
    assert authorization.stage == models.STAGE
    assert authorization.provider_execution_authorized is False
    assert authorization.archive_selection_authorized is False
    assert authorization.benchmark_estimation_authorized is False
    assert authorization.qa_release_authorized is False


def test_exact_predecessor_independent_audit_is_frozen(products: models.Products) -> None:
    freeze = products.predecessor_freeze
    assert (freeze.file_count, freeze.total_byte_count) == (21, 99_487)
    assert (freeze.manifest_member_count, freeze.manifest_member_bytes) == (20, 96_276)
    assert freeze.manifest_id == models.PREDECESSOR_MANIFEST_ID
    assert freeze.artifact_root == models.PREDECESSOR_ARTIFACT_ROOT
    assert freeze.report_id == models.PREDECESSOR_REPORT_ID
    assert freeze.decision_id == models.PREDECESSOR_DECISION_ID
    assert freeze.transition_id == models.PREDECESSOR_TRANSITION_ID
    assert freeze.prior_semantic_depth_distribution == {"0": 1, "1": 6, "2": 1}
    assert freeze.prior_semantic_depth_three_plus_count == 0
    assert freeze.formal_bytes_modified is False


def test_exact_git_source_and_registry_authority(products: models.Products) -> None:
    binding = products.source_binding
    assert binding.resolved_commit == _git("rev-parse", "HEAD")
    assert binding.resolved_tree == _git("rev-parse", "HEAD^{tree}")
    assert tuple(item.relative_path for item in binding.members) == models.SOURCE_PATHS
    assert len(binding.members) == 5
    assert all(item.bytes_equal for item in binding.members)
    registry = products.registry_binding
    assert registry.extension_operator_count == 3
    assert registry.extension_operator_ids == (
        "absolute_percentage_point_gap",
        "scale_ratio_percent",
        "signed_percentage_point_gap",
    )
    assert registry.all_extension_roles_semantic is True
    assert registry.executor_oracle_class_pairs_distinct is True


def test_two_real_topologies_reach_exact_semantic_depth_three(
    products: models.Products,
) -> None:
    audit = products.coverage_audit
    assert tuple(row.case_id for row in audit.rows) == models.CASE_IDS
    assert tuple(sorted({row.task_type for row in audit.rows})) == models.TASK_TYPES
    assert {row.topology_kind for row in audit.rows} == {
        "serial_chain",
        "branch_and_merge",
    }
    assert audit.case_count == audit.topology_count == 2
    assert audit.semantic_depth_three_plus_count == 2
    assert audit.semantic_depth_distribution == {"3": 2}
    assert audit.structural_depth_distribution == {"4": 2}
    assert audit.workflow_depth_distribution == {"5": 2}
    by_case = {row.case_id: row for row in audit.rows}
    assert by_case["serial_margin_target_gap"].operator_sequence == (
        "lookup",
        "lookup",
        "lookup",
        "ratio",
        "scale_ratio_percent",
        "signed_percentage_point_gap",
    )
    assert by_case["serial_margin_target_gap"].semantic_transition_sequence == (
        "ratio",
        "scale_ratio_percent",
        "signed_percentage_point_gap",
    )
    assert by_case["branch_merge_growth_gap"].operator_sequence == (
        "lookup",
        "lookup",
        "lookup",
        "lookup",
        "growth",
        "growth",
        "signed_percentage_point_gap",
        "absolute_percentage_point_gap",
    )
    assert by_case["branch_merge_growth_gap"].semantic_transition_sequence == (
        "growth|growth",
        "signed_percentage_point_gap",
        "absolute_percentage_point_gap",
    )
    assert {item.semantic_operation_depth for item in products.depth_metrics} == {3}
    assert {item.structural_dependency_depth for item in products.depth_metrics} == {4}
    assert {item.workflow_interaction_depth for item in products.depth_metrics} == {5}
    assert all(item.output_dependency_closed for item in products.depth_metrics)


def test_execution_replay_answer_citation_and_quality_all_pass(
    products: models.Products,
) -> None:
    assert len(products.executions) == len(products.verification_reports) == 2
    assert all(item.independent_verification.passed for item in products.executions)
    assert all(all(item.gates.values()) for item in products.executions)
    assert all(item.passed for item in products.verification_reports)
    assert all(item.decision == ReleaseDecision.ACCEPTED for item in products.assessments)
    assert {item.program_execution.final_output["unit"] for item in products.executions} == {
        "percentage_points"
    }
    assert {item.program_execution.final_output["value"] for item in products.executions} == {
        "5.0",
        "5.00",
    }
    audit = products.coverage_audit
    assert audit.complete_execution_count == audit.independent_replay_count == 2
    assert (
        audit.answer_schema_correct_count
        == audit.answer_correct_count
        == audit.citation_correct_count
        == audit.evaluator_accepted_count
        == 2
    )


def test_seven_source_depth_topology_and_verifier_attacks_reject(
    products: models.Products,
) -> None:
    audit = products.negative_audit
    assert tuple(item.name for item in audit.controls) == models.NEGATIVE_CONTROL_NAMES
    assert (audit.attempted_count, audit.rejected_count, audit.accepted_count) == (7, 7, 0)
    assert audit.candidate_rehashed_count == 7
    assert audit.original_answer_bytes_retained_count == 5
    assert all(item.rejected for item in audit.controls)
    assert all(item.output_writes == item.provider_calls == 0 for item in audit.controls)
    assert {item.rejection_stage for item in audit.controls} == {
        "output_dependency_closure",
        "exact_source_program_admission",
        "pattern_source_admission",
        "verifier_evaluator_admission",
        "authoritative_registry_metric_admission",
    }


def test_historical_registered_eight_type_catalog_is_not_modified() -> None:
    assert tuple(sorted(FinanceTaskPlugin.task_family_ids)) == (
        "comparison",
        "derived_growth_comparison",
        "fact_retrieval",
        "registered_cross_metric_comparison",
        "registered_ratio",
        "temporal_absolute_change",
        "temporal_average",
        "temporal_growth",
    )


def test_gates_scope_decision_and_transition_are_narrow(products: models.Products) -> None:
    scope = products.scope_audit
    assert products.gate.passed_count == 8 and products.gate.failed_count == 0
    assert len(products.gate.gates) == 8 and all(products.gate.gates.values())
    assert not any(
        (
            scope.provider_calls,
            scope.credential_lookups,
            scope.gpu_jobs,
            scope.archive_selections,
            scope.benchmark_rows,
            scope.empirical_estimates,
            scope.online_job_manifests,
            scope.qa_release_objects,
            scope.vtdo_rows,
            scope.training_rows,
            scope.production_rows,
        )
    )
    assert scope.existing_registered_catalog_modified is False
    assert scope.claim_is_constructibility_only is True
    assert products.decision.archive_grounding_established is False
    assert products.decision.benchmark_distribution_established is False
    assert products.decision.release_eligibility_established is False
    assert products.transition.next_stage == models.NEXT_STAGE
    assert products.transition.next_stage_authorized is True
    assert products.transition.provider_execution_authorized is False
    assert products.transition.archive_selection_authorized is False
    assert products.transition.benchmark_estimation_authorized is False
    assert products.transition.qa_release_authorized is False


def test_artifact_build_is_deterministic_and_self_excluding(
    products: models.Products, tmp_path: Path
) -> None:
    left = tmp_path / "left"
    right = tmp_path / "right"
    write_qa_semantic_depth_three_plus_artifacts(products, left)
    write_qa_semantic_depth_three_plus_artifacts(products, right)
    assert _files(left) == _files(right)
    files = _files(left)
    manifest = json.loads(files["artifact_manifest.json"])
    assert manifest["self_excluding"] is True
    assert manifest["file_count"] == len(files) - 1 == 20
    assert "artifact_manifest.json" not in {item["relative_path"] for item in manifest["members"]}
    for item in manifest["members"]:
        payload = files[item["relative_path"]]
        assert item["sha256"] == hashlib.sha256(payload).hexdigest()
        assert item["byte_count"] == len(payload)
    assert files["external_review.txt"] == AUDIT.read_bytes()
    assert files["operator_directive.txt"] == models.OPERATOR_DIRECTIVE.encode("utf-8")


def test_changed_external_review_rejects(tmp_path: Path) -> None:
    changed = tmp_path / "changed.txt"
    changed.write_bytes(AUDIT.read_bytes() + b"\n")
    with pytest.raises(ValueError, match="external semantic-depth audit bytes differ"):
        build_qa_semantic_depth_three_plus_preflight(
            repo_root=ROOT,
            external_audit_path=changed,
            source_commit=_git("rev-parse", "HEAD"),
            source_tree=_git("rev-parse", "HEAD^{tree}"),
        )
