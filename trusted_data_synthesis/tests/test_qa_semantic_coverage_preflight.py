from __future__ import annotations

import hashlib
import inspect
import json
from pathlib import Path

import pytest

from trusted_synthesis.canonical_json import strict_canonical_hash
from trusted_synthesis.core.trajectory.public_plan_executor import (
    PublicPlanCandidateExecution,
    PublicPlanCandidateExecutor,
)
from trusted_synthesis.experiments.qa_semantic_coverage.preflight import (
    BASELINE_ARTIFACT_ROOT,
    BASELINE_MANIFEST_ID,
    EXPECTED_TASK_TYPES,
    OfflineQAPreflightReport,
    SemanticCoverageRow,
    build_offline_qa_semantic_coverage_preflight,
    executor_source_has_task_type_branch,
    write_offline_qa_semantic_coverage_artifacts,
)

_REPO_ROOT = Path(__file__).resolve().parents[2]
_AUDIT = Path(
    "/home/zhuxinrui/.codex/attachments/ba6e48e8-35aa-4424-beed-292f39422483/pasted-text.txt"
)
_FORMAL = (
    _REPO_ROOT / "trusted_data_synthesis/artifacts/qa_semantic_coverage/"
    "offline_qa_semantic_type_coverage_program_depth_closure_v1_20260903"
)


@pytest.fixture(scope="module")
def products():
    return build_offline_qa_semantic_coverage_preflight(
        repo_root=_REPO_ROOT,
        external_audit_path=_AUDIT,
        source_commit="0" * 40,
        source_tree="1" * 40,
    )


def test_baseline_freezes_actual_single_type_surface_pool(products) -> None:
    baseline = products.baseline

    assert baseline.baseline_manifest_id == BASELINE_MANIFEST_ID
    assert baseline.baseline_artifact_root == BASELINE_ARTIFACT_ROOT
    assert baseline.file_count == 18
    assert baseline.manifest_member_count == 17
    assert baseline.byte_count == 1_233_274
    assert baseline.semantic_instance_count == 4
    assert baseline.surface_candidate_count == 16
    assert baseline.selected_surface_count == 8
    assert baseline.task_type_count == baseline.topology_count == baseline.answer_schema_count == 1
    assert baseline.semantic_depth_distribution == {"1": 4}
    assert baseline.surface_depth_distribution == {"1": 16}
    assert baseline.renderer_count_per_instance == 4
    assert baseline.non_null_program_execution_count == 0


def test_existing_eight_type_catalog_and_six_registered_pairs_close(products) -> None:
    census = products.census

    assert census.registered_task_type_count == census.materialized_task_type_count == 8
    assert set(census.task_type_distribution) == set(EXPECTED_TASK_TYPES)
    assert census.task_type_distribution == {
        "comparison": 1,
        "derived_growth_comparison": 1,
        "fact_retrieval": 1,
        "registered_cross_metric_comparison": 6,
        "registered_ratio": 1,
        "temporal_absolute_change": 1,
        "temporal_average": 1,
        "temporal_growth": 1,
    }
    assert census.semantic_instance_count == 13
    assert census.surface_realization_count == 26
    assert census.renderer_count_per_instance == 2
    assert census.topology_count == 8
    assert census.parameterized_program_count == 13
    assert census.answer_schema_count == 7
    assert census.registered_comparison_pairs == (
        "current_assets/current_liabilities",
        "operating_cash_flow/net_income",
        "revenue/gross_profit",
        "revenue/net_income",
        "revenue/operating_income",
        "total_assets/total_liabilities",
    )


def test_program_depth_is_semantic_and_nodewise_execution_is_total(products) -> None:
    census = products.census

    assert census.semantic_depth_distribution == {"1": 8, "2": 4, "3": 1}
    assert census.node_count_distribution == {"1": 8, "3": 3, "4": 1, "7": 1}
    assert census.non_null_program_execution_count == 13
    assert census.independently_replayed_execution_count == 13
    assert census.exact_plan_trajectory_match_count == 13
    assert census.quality_accepted_count == 13
    assert all(row.program_execution_non_null for row in census.rows)
    assert all(row.executed_plan_node_count == row.node_count for row in census.rows)
    assert all(row.independently_replayed_node_count == row.node_count for row in census.rows)
    assert all(row.plan_to_trajectory_exact for row in census.rows)
    assert all("evidence.search" in row.tool_capabilities for row in census.rows)
    assert all(
        row.tool_capabilities == ("evidence.search",)
        if row.task_type == "fact_retrieval"
        else row.tool_capabilities == ("calculator", "evidence.search")
        for row in census.rows
    )
    derived = next(row for row in census.rows if row.task_type == "derived_growth_comparison")
    assert derived.node_count == 7
    assert derived.edge_count == 6
    assert derived.semantic_only_depth == 3


def test_public_executor_never_reads_hidden_oracle_as_behavior_source(products) -> None:
    generate_source = inspect.getsource(PublicPlanCandidateExecutor.generate)

    assert ".oracle" not in generate_source
    assert not executor_source_has_task_type_branch()
    assert all(execution.independent_verification.passed for execution in products.executions)
    assert all(
        len(
            {
                step.program_node_id
                for step in execution.trajectory.steps
                if step.program_node_id is not None
                and step.action.value in {"select_evidence", "calculate"}
            }
        )
        == execution.actual_node_count
        for execution in products.executions
    )


def test_data_driven_answer_projection_covers_fact_and_derived_outputs(products) -> None:
    by_type = {
        row.task_type: execution
        for row, execution in zip(products.census.rows, products.executions, strict=True)
    }
    # Rows are content-sorted independently of executions, so resolve by task ID when necessary.
    execution_by_task = {
        execution.trajectory.task_id: execution for execution in products.executions
    }
    package_by_type = {
        package.semantic_plan.task_type: package
        for package in products.realized_packages
        if package.realization.renderer_profile_id.endswith(".v1")
    }
    del by_type
    fact = execution_by_task[package_by_type["fact_retrieval"].task.task_id]
    derived = execution_by_task[package_by_type["derived_growth_comparison"].task.task_id]

    assert fact.trajectory.final_answer["result"]["source_id"] == "sec_companyfacts"
    assert derived.trajectory.final_answer["result"] == {
        "selected_entity_id": "QA_SEMANTIC_A",
        "selected_entity_name": "QA Semantic Company A",
        "left_entity_id": "QA_SEMANTIC_A",
        "left_entity_name": "QA Semantic Company A",
        "left_growth_pct": "35",
        "right_entity_id": "QA_SEMANTIC_B",
        "right_entity_name": "QA Semantic Company B",
        "right_growth_pct": "20",
        "difference_percentage_points": "15",
    }


def test_negative_controls_and_scope_boundary_fail_closed(products) -> None:
    audit = products.negative_controls

    assert audit.control_count == audit.rejected_count == 4
    assert audit.accepted_count == audit.output_write_count == audit.provider_call_count == 0
    assert {row["name"] for row in audit.controls} == {
        "missing_bound_evidence",
        "cross_version_evidence_substitution",
        "registry_missing_registered_compare",
        "public_plan_parameter_substitution",
    }
    assert all(products.report.gates.values())
    assert products.census.provider_call_count == 0
    assert products.census.gpu_job_count == 0
    assert products.census.development_job_count == 0
    assert products.census.vtdo_parent_count == products.census.vtdo_artifact_write_count == 0
    assert products.census.empirical_row_count == 0
    assert products.report.claim_boundary["deferred_raw_proposals"] == (
        "growth_filter_margin_rank",
        "temporal_peak_secondary_lookup",
    )


def test_artifact_build_is_byte_deterministic(products, tmp_path: Path) -> None:
    left = tmp_path / "left"
    right = tmp_path / "right"
    write_offline_qa_semantic_coverage_artifacts(products, left)
    write_offline_qa_semantic_coverage_artifacts(products, right)

    left_paths = tuple(sorted(path.name for path in left.iterdir()))
    right_paths = tuple(sorted(path.name for path in right.iterdir()))
    assert left_paths == right_paths
    assert len(left_paths) == 17
    assert all((left / name).read_bytes() == (right / name).read_bytes() for name in left_paths)


def test_formal_artifacts_revalidate_identities_and_actual_bytes() -> None:
    assert _FORMAL.is_dir()
    report = OfflineQAPreflightReport.model_validate_json((_FORMAL / "report.json").read_bytes())
    rows = tuple(
        SemanticCoverageRow.model_validate_json(line)
        for line in (_FORMAL / "coverage_rows.jsonl").read_bytes().splitlines()
        if line
    )
    executions = tuple(
        PublicPlanCandidateExecution.model_validate_json(line)
        for line in (_FORMAL / "public_plan_executions.jsonl").read_bytes().splitlines()
        if line
    )
    manifest = json.loads((_FORMAL / "artifact_manifest.json").read_bytes())

    assert len(rows) == len(executions) == 13
    assert all(report.gates.values())
    assert len(manifest["files"]) == 16
    manifest_payload = {key: value for key, value in manifest.items() if key != "manifest_id"}
    assert manifest["manifest_id"] == strict_canonical_hash(
        manifest_payload,
        prefix="offline_qa_semantic_coverage_artifact_manifest:",
    )
    assert all(
        hashlib.sha256((_FORMAL / row["filename"]).read_bytes()).hexdigest() == row["sha256"]
        and (_FORMAL / row["filename"]).stat().st_size == row["byte_count"]
        for row in manifest["files"]
    )
