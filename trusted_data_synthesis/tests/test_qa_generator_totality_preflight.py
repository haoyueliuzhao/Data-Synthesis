from __future__ import annotations

import hashlib
import json
from pathlib import Path

import pytest

from trusted_synthesis.core.evaluation.schema import ReleaseDecision
from trusted_synthesis.experiments.finance_pilot.candidate import (
    CANDIDATE_GENERATOR_VERSION,
    FINANCE_NUMERIC_GENERATOR_CONTRACT_ID,
    FinanceNumericCandidateGenerator,
)
from trusted_synthesis.experiments.qa_generator_totality.preflight import (
    DEPENDENCY_DEPTHS,
    EXTERNAL_AUDIT_BYTE_COUNT,
    EXTERNAL_AUDIT_SHA256,
    FORMAL_QA_ARTIFACT_MANIFEST_ID,
    FORMAL_QA_ARTIFACT_ROOT,
    FORMAL_QA_DECISION_ID,
    FORMAL_QA_ROW_MANIFEST_ID,
    FORMAL_QA_TRANSITION_ID,
    NEGATIVE_CONTROL_NAMES,
    NEXT_STAGE,
    OPERATOR_DIRECTIVE,
    OPERATOR_DIRECTIVE_BYTE_COUNT,
    OPERATOR_DIRECTIVE_SHA256,
    PROGRAM_NODE_COUNTS,
    REGISTERED_TASK_TYPES,
    SOURCE_PATHS,
    FinanceNumericCandidateGeneratorTotality,
    QAGeneratorTotalityProducts,
    build_qa_generator_totality_preflight,
    write_qa_generator_totality_artifacts,
)

ROOT = Path(__file__).resolve().parents[2]
AUDIT = Path(
    "/home/zhuxinrui/.codex/attachments/5fb1202b-02c2-4041-a76a-2613d9bf9c3e/pasted-text.txt"
)


def _files(root: Path) -> dict[str, bytes]:
    return {
        path.relative_to(root).as_posix(): path.read_bytes()
        for path in root.rglob("*")
        if path.is_file()
    }


@pytest.fixture(scope="module")
def products() -> QAGeneratorTotalityProducts:
    return build_qa_generator_totality_preflight(
        repo_root=ROOT,
        external_audit_path=AUDIT,
        source_commit="0" * 40,
        source_tree="1" * 40,
    )


def test_exact_external_scope_and_v7_source_binding(
    products: QAGeneratorTotalityProducts,
) -> None:
    authorization = products.authorization
    binding = products.source_binding
    audit = AUDIT.read_bytes()
    assert len(audit) == EXTERNAL_AUDIT_BYTE_COUNT == 20_012
    assert hashlib.sha256(audit).hexdigest() == EXTERNAL_AUDIT_SHA256
    assert authorization.operator_directive == OPERATOR_DIRECTIVE
    assert len(authorization.operator_directive.encode()) == OPERATOR_DIRECTIVE_BYTE_COUNT == 32
    assert hashlib.sha256(authorization.operator_directive.encode()).hexdigest() == (
        OPERATOR_DIRECTIVE_SHA256
    )
    assert products.external_review_bytes == audit
    assert products.operator_directive_bytes == OPERATOR_DIRECTIVE.encode("utf-8")
    assert authorization.operator_directive_sha256 == OPERATOR_DIRECTIVE_SHA256
    assert authorization.provider_execution_authorized is False
    assert authorization.gpu_execution_authorized is False
    assert authorization.qa_release_authorized is False
    assert binding.base_generator_contract_id == FINANCE_NUMERIC_GENERATOR_CONTRACT_ID
    assert binding.finance_numeric_candidate_v7_source_bound is True
    assert binding.registered_catalog_totalized is True
    assert (binding.source_commit, binding.source_tree) == ("0" * 40, "1" * 40)
    assert len(binding.source_files) == 14
    assert tuple(item.relative_path for item in binding.source_files) == SOURCE_PATHS
    for item in binding.source_files:
        payload = (ROOT / item.relative_path).read_bytes()
        assert item.sha256 == hashlib.sha256(payload).hexdigest()
        assert item.byte_count == len(payload)


def test_read_only_baseline_and_formal_qa_authorities_are_frozen(
    products: QAGeneratorTotalityProducts,
) -> None:
    freeze = products.baseline_scope_freeze
    assert (freeze.baseline_file_count, freeze.baseline_total_byte_count) == (
        18,
        1_233_274,
    )
    assert freeze.baseline_manifest_member_count == 17
    assert freeze.baseline_candidate_manifest_id.endswith(
        "18523303bb2fed9df208205bc7fb44e92cde6bff9d46dd179220b3a8af1990ad"
    )
    assert freeze.baseline_artifact_root.endswith(
        "9caf67aa43317415f0227b5ae6ea4f78dd5cf68a9fb0d1491436f13494081e04"
    )
    assert (freeze.formal_file_count, freeze.formal_total_byte_count) == (17, 810_715)
    assert freeze.formal_manifest_member_count == 16
    assert freeze.formal_artifact_manifest_id == FORMAL_QA_ARTIFACT_MANIFEST_ID
    assert freeze.formal_artifact_root == FORMAL_QA_ARTIFACT_ROOT
    assert freeze.formal_row_manifest_id == FORMAL_QA_ROW_MANIFEST_ID
    assert freeze.formal_decision_id == FORMAL_QA_DECISION_ID
    assert freeze.formal_transition_id == FORMAL_QA_TRANSITION_ID
    assert freeze.documentation_old_id_status == "post_freeze_erratum_only"
    assert freeze.formal_json_is_authority is True
    assert freeze.formal_json_authority_modified is False
    assert freeze.provider_calls == freeze.gpu_jobs == freeze.release_objects == 0
    assert products.report.baseline_scope_freeze_id == freeze.freeze_id


def test_exact_registered_catalog_executes_eight_of_eight(
    products: QAGeneratorTotalityProducts,
) -> None:
    audit = products.totality_audit
    assert audit.registered_task_types == REGISTERED_TASK_TYPES
    assert tuple(row.task_type for row in audit.rows) == REGISTERED_TASK_TYPES
    assert audit.registered_task_count == audit.successful_generator_branch_count == 8
    assert audit.insufficient_capability_count == 0
    assert audit.exact_program_execution_count == 8
    assert audit.exact_operation_correctness_count == 8
    assert audit.answer_schema_correct_count == 8
    assert audit.answer_correct_count == 8
    assert audit.citation_correct_count == 8
    assert audit.evaluator_accepted_count == 8
    assert len(products.bundles) == len(products.realized_packages) == 8
    assert len(products.trajectories) == len(products.assessments) == 8
    assert all(
        item.generator_version == CANDIDATE_GENERATOR_VERSION for item in products.trajectories
    )
    assert all(item.decision == ReleaseDecision.ACCEPTED for item in products.assessments)


def test_repaired_registered_tasks_have_complete_exact_program_traces(
    products: QAGeneratorTotalityProducts,
) -> None:
    by_type = {row.task_type: row for row in products.totality_audit.rows}
    assert by_type["temporal_absolute_change"].operator_sequence == (
        "lookup",
        "lookup",
        "difference",
    )
    assert by_type["registered_ratio"].operator_sequence == (
        "lookup",
        "lookup",
        "ratio",
    )
    assert by_type["derived_growth_comparison"].operator_sequence == (
        "lookup",
        "lookup",
        "lookup",
        "lookup",
        "growth",
        "growth",
        "compare",
    )
    for task_type in (
        "temporal_absolute_change",
        "registered_ratio",
        "derived_growth_comparison",
    ):
        row = by_type[task_type]
        assert row.generator_succeeded is True
        assert row.insufficient_capability is False
        assert row.executed_program_node_count == row.program_node_count
        assert row.grounded_operation_count == row.program_node_count
        assert row.independently_replayed_node_count == row.program_node_count


def test_program_node_and_dependency_depths_are_reported_separately(
    products: QAGeneratorTotalityProducts,
) -> None:
    audit = products.totality_audit
    assert audit.program_node_count_distribution == {"1": 3, "3": 3, "4": 1, "7": 1}
    assert audit.maximum_dependency_depth_distribution == {"1": 3, "2": 4, "3": 1}
    for row in audit.rows:
        assert row.program_node_count == PROGRAM_NODE_COUNTS[row.task_type]
        assert row.maximum_dependency_depth == DEPENDENCY_DEPTHS[row.task_type]
        assert row.workflow_action_count > row.maximum_dependency_depth
    derived = next(row for row in audit.rows if row.task_type == "derived_growth_comparison")
    assert (derived.program_node_count, derived.maximum_dependency_depth) == (7, 3)
    assert derived.workflow_action_count >= 11


def test_v7_execution_matches_independent_public_plan_replay(
    products: QAGeneratorTotalityProducts,
) -> None:
    for trajectory, execution, verification in zip(
        products.trajectories,
        products.executions,
        products.verification_reports,
        strict=True,
    ):
        assert trajectory.program_execution == execution.program_execution.model_dump(mode="json")
        assert trajectory.final_answer["result"] == execution.trajectory.final_answer["result"]
        assert {item["evidence_id"] for item in trajectory.final_answer["citations"]} == {
            item["evidence_id"] for item in execution.trajectory.final_answer["citations"]
        }
        assert verification.passed is True
        assert verification.executed_program_node_count == execution.actual_node_count
        assert verification.grounded_operation_count == execution.actual_node_count
        assert execution.independent_verification.passed is True


def test_exact_six_source_and_semantic_negative_controls_reject(
    products: QAGeneratorTotalityProducts,
) -> None:
    audit = products.negative_audit
    assert tuple(item.name for item in audit.controls) == NEGATIVE_CONTROL_NAMES
    assert (audit.attempted_count, audit.rejected_count, audit.accepted_count) == (6, 6, 0)
    assert audit.output_write_count == audit.provider_calls == audit.gpu_jobs == 0
    assert all(item.rejected for item in audit.controls)
    assert all(item.output_writes == item.provider_calls == 0 for item in audit.controls)
    assert {item.rejection_stage for item in audit.controls} == {
        "generator_source_admission",
        "verifier_evaluator_admission",
    }


def test_scope_and_transition_forbid_provider_gpu_and_release(
    products: QAGeneratorTotalityProducts,
) -> None:
    scope = products.scope_audit
    report = products.report
    assert scope.canonical_case_count == 8
    assert scope.provider_calls == scope.credential_lookups == scope.gpu_jobs == 0
    assert scope.online_job_manifests == scope.empirical_rows == 0
    assert scope.qa_release_objects == scope.vtdo_rows == 0
    assert scope.training_rows == scope.production_rows == 0
    assert report.passed_count == 8 and report.failed_count == 0
    assert len(report.gates) == 8 and all(report.gates.values())
    assert report.next_stage == NEXT_STAGE
    assert report.provider_execution_authorized is False
    assert report.gpu_execution_authorized is False
    assert report.qa_release_authorized is False
    assert report.archive_grounding_claimed is False
    assert report.realistic_difficulty_claimed is False


def test_artifact_build_is_deterministic_and_manifest_is_self_excluding(
    products: QAGeneratorTotalityProducts, tmp_path: Path
) -> None:
    left = tmp_path / "left"
    right = tmp_path / "right"
    write_qa_generator_totality_artifacts(products, left)
    write_qa_generator_totality_artifacts(products, right)
    assert _files(left) == _files(right)
    files = _files(left)
    manifest = json.loads(files["artifact_manifest.json"])
    assert manifest["self_excluding"] is True
    assert manifest["file_count"] == len(files) - 1 == 18
    assert "artifact_manifest.json" not in {item["relative_path"] for item in manifest["members"]}
    for item in manifest["members"]:
        payload = files[item["relative_path"]]
        assert item["sha256"] == hashlib.sha256(payload).hexdigest()
        assert item["byte_count"] == len(payload)
    assert files["external_review.txt"] == AUDIT.read_bytes()
    assert len(files["external_review.txt"]) == EXTERNAL_AUDIT_BYTE_COUNT
    assert hashlib.sha256(files["external_review.txt"]).hexdigest() == EXTERNAL_AUDIT_SHA256
    assert files["operator_directive.txt"] == OPERATOR_DIRECTIVE.encode("utf-8")
    assert len(files["operator_directive.txt"]) == OPERATOR_DIRECTIVE_BYTE_COUNT
    assert hashlib.sha256(files["operator_directive.txt"]).hexdigest() == (
        OPERATOR_DIRECTIVE_SHA256
    )
    transition = json.loads(files["transition.json"])
    assert transition["next_stage"] == NEXT_STAGE
    assert transition["provider_execution_authorized"] is False
    assert transition["qa_release_authorized"] is False


def test_generator_adapter_is_a_real_finance_numeric_generator() -> None:
    assert issubclass(FinanceNumericCandidateGeneratorTotality, FinanceNumericCandidateGenerator)
    assert CANDIDATE_GENERATOR_VERSION == "finance_numeric_candidate.v7"
